import json
import slack
import os, shlex, subprocess
from pathlib import Path
import datetime
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import pdb


env_file= json.load(open(Path('.')/'env.json'))
app = Flask(__name__) # represents the name of the file 
slack_event_adapter = SlackEventAdapter(env_file["slack_sign_secret"], '/slack/events', app)

client = slack.WebClient(token=env_file['slack_token'])
bot_id = client.api_call("auth.test")["user_id"]



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
                     print_msg("#testqa", "command failed "+str(out[1]))
                     break
       return status

def push_changes():
       
       UAT_status = git_commands(env_file["US-UAT_commands"])
       #ZAT_status = git_commands(env_file["Zurich-UAT_commands"])
       #print("yes")
       if not UAT_status:
              print_msg("#testqa", "GIT push failed for US UAT ")

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
       if data['text'].lower() == "yes":
              print_msg("#chamber-of-secrets", "GIT Push approved by "+ data['user_name'])
       elif data['text'].lower() == "no":
              print_msg("#chamber-of-secrets", "GIT Push denied by "+ data['user_name'])
       else:
              print_msg("#chamber-of-secrets", "Invalid command received. Accepted command '/qa_git_push_cmd yes or /qa_git_push_cmd no' ")

       return Response(), 200

def send_scheduled_messages_channel(message):

       msg_ids=[]
       for msg in message:
              scheduledTime=(datetime.datetime.now()+ datetime.timedelta(minutes=1)).strftime('%s')
              msg_id = client.chat_scheduleMessage(
                     token=env_file['slack_token'], channel = msg['channel_id'], text = msg['text'], post_at = scheduledTime
              )
              msg_ids.append(msg_id)
       return msg_ids


if __name__=='__main__':
       send_scheduled_messages_channel(env_file['scheduled_message'])
       app.run(port=5000)