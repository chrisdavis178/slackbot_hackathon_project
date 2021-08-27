import json
import slack, time
import os, shlex, subprocess, re, sched, threading
from pathlib import Path
import datetime as dt
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
from datetime import datetime
import pdb

env_file= json.load(open(Path('.')/'env.json'))
app = Flask(__name__) # represents the name of the file 
slack_event_adapter = SlackEventAdapter(env_file["slack_sign_secret"], '/slack/events', app)

client = slack.WebClient(token=env_file['slack_token'])
bot_id = client.api_call("auth.test")["user_id"]
s = sched.scheduler(time.time, time.sleep)
branch_list = {}

class BranchInfo:

  DIVIDER = {'type' : 'divider'}

  def __init__(self, branch_name):
    self.branch_name = branch_name
    self.scheduled = False
    self.scheduled_at = None
    self.updated_by = None
    self.jobid = None
    self.icon_emoji = ':rooster:'
    self.timestamp = ''

  def get_message(self):
    return {
      'ts': self.timestamp,
      'channel': '#chamber-of-secrets',
      'branch_name': self.branch_name,
      'Scheduled_status': self.scheduled,
      'Status_updated_by': self.updated_by,
      'icon_emoji': ':rooster:',
      'blocks':[
        self._get_status(),
        self.DIVIDER,
        self._get_details()
      ]
    }

  def _get_details(self):
    text = {
            'Branch name': self.branch_name
       }
    if self.updated_by:
      text['Updated by'] = self.updated_by
      text['Updated on'] = self.timestamp

    if self.scheduled:
      text['Scheduled at'] = self.scheduled_at

    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': json.dumps(text, indent=4, sort_keys=True)  }}

  def _get_status(self):
    checkmark = ':x:'
    text = f'{checkmark}' 
    if self.scheduled:
      checkmark = ':white_check_mark:'
      text = f"{checkmark}"

    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text }}

def initialize_branch():
    for b in env_file['branches']:
       branch_info = BranchInfo(b)
       branch_list[b] = branch_info

def execute_cmds(command, shellenable=False):
    if not shellenable:
       cmd=shlex.split(command)
    else:
       cmd=command
    query = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shellenable)
    try:
        out,err = query.communicate()
        if query.returncode!=0:
            #return (query.returncode, "stderr:"+err.strip() + " :stdout:" + out.strip())
            return (query.returncode, err.strip())
        else:
            return (0,out)
    except Exception as e:
        query.terminate()
        return (1,str(e))

def print_msg(channel2,msg):
       client.chat_postMessage(channel=channel2, text=msg)

def git_commands(gitcmds):
       status=True
       for gitcmd in gitcmds:
              out = execute_cmds(gitcmd)
              if out!=0:
                     status=False
                     print_msg("#chamber-of-secrets", "command failed "+str(out[1]))
                     break
       return status

def push_changes():
       
       UAT_status = git_commands(env_file["US-UAT_commands"])
       #ZAT_status = git_commands(env_file["Zurich-UAT_commands"])
       #print("yes")
       if not UAT_status:
              print_msg("#chamber-of-secrets", "GIT push failed for US UAT ")

def execute_commands():
  print_msg("#chamber-of-secrets","Excuting shell commands place holder ")

# to handle msg in events
@slack_event_adapter.on('message')
def message(payload): # payload is the data sent by slack event
       event = payload.get('event', {}) # looks for key work event, if not empty dict
       channel_id= event.get('channel') # gets channel id
       user_id= event.get('user')
       text= event.get('text')

       if user_id != bot_id: # to avoid the infinite loop
              if "status" in text.lower():
                text = text.split()
                branch = text[1] if len(text) > 1 else 'all'
                get_status(branch)

# adding end point to server
@app.route('/qa_git_push_cmd',   methods=['GET','POST'])
def qa_git_push():
        data = request.form
        p = re.compile('("|\')')
        all_text = p.sub('', data['text'])
        all_text = all_text.split()
        branch, cmd = (all_text[0],all_text[1]) if len(all_text) > 1 else (None, all_text[0])
        shour, smin = env_file['deploy_at'].split(':')
       
        if branch is None:
          print_msg("#chamber-of-secrets",":ghost: Whoops!!! missing branch name")
          return Response(), 200 # changing return code generate dispatch fail msg
       
        if branch not in env_file['branches']:
          print_msg("#chamber-of-secrets",":ghost: Whoops!!! Couldnt find the branch '{}' in the list ".format(branch))
          return Response(), 200 

        if cmd.lower() == "yes":              
          scheduletime=datetime.today().replace(hour=int(shour), minute=int(smin), second =0, microsecond=0)
          jobid = s.enterabs(scheduletime.timestamp(), 1, execute_commands)
          t = threading.Thread(target=s.run)
          t.start()
          curr_branch = branch_list[branch]
          curr_branch.scheduled = True
          curr_branch.updated_by = data['user_name']
          curr_branch.scheduled_at = env_file['deploy_at']
          curr_branch.jobid = jobid
          curr_branch.timestamp = dt.datetime.now().strftime("%b %d %Y  %H:%M:%S")
          get_status(branch)
          print_msg("#chamber-of-secrets", " :ninja: GIT Push scheduled by "+ data['user_name'])
          #t.join()
        elif cmd.lower() == "no":
          curr_branch = branch_list[branch]
          if curr_branch.scheduled:
            scheduletime=datetime.today().replace(hour=int(shour), minute=int(smin), second =0, microsecond=0)
            if scheduletime.timestamp() - dt.datetime.now().timestamp() >0:
              s.cancel(curr_branch.jobid) 
            curr_branch.scheduled = False
            curr_branch.updated_by = data['user_name']
            curr_branch.timestamp = dt.datetime.now().strftime("%b %d %Y  %H:%M:%S")
            get_status(branch)
            print_msg("#chamber-of-secrets", ":rooster: Git push scheduled cancelled by "+ data['user_name'])
          else:
            get_status(branch)
            print_msg("#chamber-of-secrets", ":shipit: Operation denied as the scheduled is cancelled by "+ data['user_name'])
        elif cmd.lower() == "now":
            print_msg("#chamber-of-secrets", ":shrug: Deploying the code now .... :man-running: :dash:")
            execute_commands()
        else:
            print_msg("#chamber-of-secrets", "Invalid command received. Accepted command '/qa_git_push_cmd <branch> yes or /qa_git_push_cmd <branch> no /qa_git_push_cmd <branch> now' ")

        return Response(), 200

def send_scheduled_messages_channel():
       msg_ids=[]
       for branch in env_file['scheduled_message']:
              scheduledTime=(dt.datetime.now()+ dt.timedelta(minutes=600)).strftime('%s')
              msg_id = client.chat_scheduleMessage(
                     token=env_file['slack_token'], channel = env_file['scheduled_message'][branch]['channel_id'], text = env_file['scheduled_message'][branch]['text'], post_at = scheduledTime
              )
              msg_ids.append(msg_id)
       return msg_ids

#@app.route('/',   methods=['GET','POST'])
def get_status(branch='all'):
  if branch.lower() != "all" and branch not in env_file['branches']:
    print_msg("#chamber-of-secrets","Whoops!!! Couldnt find the branch '{}' in the list ".format(branch))
    return

  if branch.lower() == "all":
    for b in env_file['branches']:
      branch_info = branch_list[b]
      status = branch_info.get_message()
      client.chat_postMessage(**status)
  else:
      branch_info = branch_list[branch]
      status = branch_info.get_message()
      client.chat_postMessage(**status)    

def schedule_loop():
   while True:
      schedule.run_pending()
      time.sleep(1)

if __name__=='__main__':
  initialize_branch()
  send_scheduled_messages_channel() 
  app.run(port=5000)
  