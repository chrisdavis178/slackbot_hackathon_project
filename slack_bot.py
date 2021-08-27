import json
import slack, time
import os, shlex, subprocess, re, sched, threading
from pathlib import Path
import datetime as dt
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
from datetime import datetime
import pdb
import smtplib

env_file= json.load(open(Path('.')/'env.json'))
app = Flask(__name__) # represents the name of the file 
slack_event_adapter = SlackEventAdapter(env_file["slack_sign_secret"], '/slack/events', app)

client = slack.WebClient(token=env_file['slack_token'])
bot_id = client.api_call("auth.test")["user_id"]
s = sched.scheduler(time.time, time.sleep)
branch_list = {}

INTEGRATION_BRANCH = 'integration'
UAT_US_BRANCH = 'us-uat'
UAT_ZURICH_BRANCH = 'zurich-uat'
MASTER_BRANCH = 'main'
class GitBranchDeletionFailure(Exception):
       pass
class GitBranchCheckoutFailure(Exception):
       pass
class GitPullFailure(Exception):
       pass
class GitPushFailure(Exception):
       pass
class GitBranchCreationFailure(Exception):
       pass
class CommandFailed(Exception):
       pass
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
    self.deployed = None

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

    if not self.deployed and self.scheduled:
      text['Scheduled at'] = self.scheduled_at
      
    if self.deployed:
      text['Deployed'] = self.deployed
     
    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': json.dumps(text, indent=4, sort_keys=True)  }}

  def _get_status(self):
    checkmark = ':x:'
    if self.scheduled or self.deployed:
      checkmark = ':white_check_mark:'

    text = f"{checkmark}"
    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text }}

def initialize_branch():
    for b in env_file['branches']:
       branch_info = BranchInfo(b)
       branch_list[b] = branch_info

def send_email_notification(message):
       try:
              smtp = smtplib.SMTP('smtp.gmail.com',587)
              smtp.ehlo()
              smtp.starttls()
              smtp.ehlo()
              smtp.login('yyabijaiy@gmail.com', 'Bangalore@97')
              subject = 'GIT PUSH STATUS'
              body = message
              msg = f'Subject: {subject}\n\n{body}'
              smtp.sendmail('yyabijaiy@gmail.com', 'yyabijaiy@gmail.com', message)
       except Exception as e:
              print_msg("#chamber-of-secrets", str(e))

def send_status_notification(return_status, branch_name, message = ""):
       if return_status:
              print_msg("#chamber-of-secrets", "GIT Push was successful from {}".format(branch_list[branch_name].updated_by))
              # send_email_notification("GIT Push was successful from {} with following message {}".format(branch_list[branch_name].updated_by, message))
       else:
              print_msg("#chamber-of-secrets", "GIT Push failed from {} with Error {} ".format(branch_list[branch_name].updated_by, message))
              # send_email_notification("GIT Push failed with Error {} ".format(branch_list[branch_name].updated_by, message))

def execute_cmds(command, branch_name, shellenable=False):
    print ("INSIDE Executing")
    if not shellenable:
       cmd=shlex.split(command)
    else:
       print("executing")
       cmd=command
    query = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shellenable)
    try:
        out,err = query.communicate()
        print (str(out))
        if query.returncode!=0:
            # print("stderr:"+str(err.strip()) + " :stdout:" + str(out.strip()))
            #return (query.returncode, "stderr:"+err.strip() + " :stdout:" + out.strip())
            raise CommandFailed
        else:
            return (0,out)
    except Exception as e:
        send_status_notification(False, branch_name, str(err.strip()))
        query.terminate()
        raise CommandFailed

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
'''
def push_changes():
       UAT_status = git_commands(env_file["US-UAT_commands"])
       #ZAT_status = git_commands(env_file["Zurich-UAT_commands"])
       #print("yes")
       if not UAT_status:
              print_msg("#chamber-of-secrets", "GIT push failed for US UAT ")
'''

def execute_commands():
  print_msg("#chamber-of-secrets","Excuting shell commands place holder ")

def git_delete_branch(branch_name):
       try:
              execute_cmds('git branch -d %s' % branch_name, branch_name)
       except:
              raise GitBranchDeletionFailure

def git_checkout_branch(branch_name, create_branch_if_not_there=False):
       try:
              if create_branch_if_not_there:
                     execute_cmds('git checkout -b %s' % branch_name, branch_name)
              else:
                     execute_cmds('git checkout %s' % branch_name, branch_name)
       except:
              raise GitBranchCheckoutFailure

def git_create_branch(branch_name):
       try:
              git_checkout_branch(branch_name, True)
       except:
              raise GitBranchCreationFailure

def git_pull(branch_name):
       try:
              execute_cmds('git pull origin %s' % branch_name, branch_name)
       except:
              raise GitPullFailure

def git_push(branch_name):
       try:
              execute_cmds('git push -f origin %s' % branch_name, branch_name)
       except:
              raise GitPushFailure

def run_deployment_git_commands(branch_name):
       try:
              print("Executing Commands")
              git_delete_branch(branch_name)
              git_checkout_branch(MASTER_BRANCH)
              git_pull(MASTER_BRANCH)
              git_create_branch(branch_name)
              git_push(branch_name)
              send_status_notification(True, branch_name)
              branch_list[branch_name].deployed = ':large_green_circle:'
       except GitBranchDeletionFailure:
              pass
       except GitBranchCheckoutFailure:
              pass
       except GitPullFailure:
              pass
       except GitBranchCreationFailure:
              pass
       except GitPushFailure:
              pass

'''
def check_deployment_answer(environment, answer):
       if answer == "yes":
              print_msg("#chamber-of-secrets", "GIT Push approved by "+ data['user_name'])
       elif answer == "no":
              print_msg("#chamber-of-secrets", "GIT Push denied by "+ data['user_name'])
       else:
              print_msg("#chamber-of-secrets", "Invalid command received. Accepted command '/qa_git_push_cmd yes or /qa_git_push_cmd no' ")

# to handle msg in events
@slack_event_adapter.on('message')
def message(payload): # payload is the data sent by slack event
       event = payload.get('event', {}) # looks for key work event, if not empty dict
       channel_id= event.get('channel') # gets channel id
       user_id= event.get('user')
       text= event.get('text')
       if user_id != bot_id: # to avoid the infinite loop
              client.chat_postMessage(channel="#chamber-of-secrets", text=text)
# adding end point to server
@app.route('/qa_git_push_cmd',   methods=['GET','POST'])
def qa_git_push():
       data = request.form
       check_deployment_answer('QA', data['text'].lower())
       return Response(), 200
@app.route('/integration_git_push_cmd',   methods=['GET','POST'])
def int_git_push():
       data = request.form
       check_deployment_answer('Integration', data['text'].lower())
       return Response(), 200
@app.route('/uat_us_git_push_cmd',   methods=['GET','POST'])
def uat_us_git_push():
       data = request.form
       check_deployment_answer('UAT US', data['text'].lower())
       run_deployment_git_commands('us-uat')
       return Response(), 200
@app.route('/uat_zurich_git_push_cmd',   methods=['GET','POST'])
def uat_zurich_git_push():
       data = request.form
       check_deployment_answer('UAT ZURICH', data['text'].lower())
       run_deployment_git_commands('zurich-uat')
       return Response(), 200 
'''
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
        curr_branch = branch_list[branch]
        if cmd.lower() == "yes":              
          scheduletime=datetime.today().replace(hour=int(shour), minute=int(smin), second =0, microsecond=0)
          jobid = s.enterabs(scheduletime.timestamp(), 1, run_deployment_git_commands, argument = (branch,))
          t = threading.Thread(target=s.run)
          t.start()
          
          curr_branch.scheduled = True
          curr_branch.updated_by = data['user_name']
          curr_branch.scheduled_at = env_file['deploy_at']
          curr_branch.jobid = jobid
          curr_branch.timestamp = dt.datetime.now().strftime("%b %d %Y  %H:%M:%S")
          curr_branch.deployed = None
          get_status(branch)
          print_msg("#chamber-of-secrets", " :ninja: GIT Push scheduled by "+ data['user_name'])
          #t.join()
        elif cmd.lower() == "no":
          if curr_branch.scheduled:
            scheduletime=datetime.today().replace(hour=int(shour), minute=int(smin), second =0, microsecond=0)
            if scheduletime.timestamp() - dt.datetime.now().timestamp() >0:
              s.cancel(curr_branch.jobid) 
            curr_branch.scheduled = False
            curr_branch.updated_by = data['user_name']
            curr_branch.timestamp = dt.datetime.now().strftime("%b %d %Y  %H:%M:%S")
            curr_branch.deployed = None
            get_status(branch)
            print_msg("#chamber-of-secrets", ":rooster: Git push scheduled cancelled by "+ data['user_name'])
          else:
            get_status(branch)
            print_msg("#chamber-of-secrets", ":shipit: Operation denied as the scheduled is cancelled by "+ data['user_name'])
        elif cmd.lower() == "now":
            print_msg("#chamber-of-secrets", ":shrug: Deploying the code now .... :man-running: :dash:")
            curr_branch.updated_by = data['user_name']
            curr_branch.timestamp = dt.datetime.now().strftime("%b %d %Y  %H:%M:%S")
            run_deployment_git_commands(branch)
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
  