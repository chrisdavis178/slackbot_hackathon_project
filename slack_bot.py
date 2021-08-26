import json
import slack
import os, shlex, subprocess
from pathlib import Path
import datetime
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import pdb


#env_file= json.load(open(Path('.')/'env.json'))
#app = Flask(__name__) # represents the name of the file 
#slack_event_adapter = SlackEventAdapter(env_file["slack_sign_secret"], '/slack/events', app)
#client = slack.WebClient(token=env_file['slack_token'])
#bot_id = client.api_call("auth.test")["user_id"]


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


def execute_cmds(command, shellenable=False):
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
                     print("stderr:"+str(err.strip()) + " :stdout:" + str(out.strip()))
                     #return (query.returncode, "stderr:"+err.strip() + " :stdout:" + out.strip())
                     raise CommandFailed
              else:
                     return (0,out)
       except Exception as e:
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
                     print_msg("#testqa", "command failed "+str(out[1]))
                     break
       return status

def push_changes():
       
       UAT_status = git_commands(env_file["US-UAT_commands"])
       #ZAT_status = git_commands(env_file["Zurich-UAT_commands"])
       #print("yes")
       if not UAT_status:
              print_msg("#testqa", "GIT push failed for US UAT ")

def git_delete_branch(branch_name):
       try:
              execute_cmds('git branch -d %s' % branch_name)
       except:
              raise GitBranchDeletionFailure


def git_checkout_branch(branch_name, create_branch_if_not_there=False):
       try:
              if create_branch_if_not_there:
                     execute_cmds('git checkout -b %s' % branch_name)
              else:
                     execute_cmds('git checkout %s' % branch_name)
       except:
              raise GitBranchCheckoutFailure


def git_create_branch(branch_name):
       try:
              git_checkout_branch(environment, True)
       except:
              raise GitBranchCreationFailure


def git_pull(branch_name):
       try:
              execute_cmds('git pull origin %s' % branch_name)
       except:
              raise GitPullFailure


def git_push(branch_name):
       try:
              execute_cmds('git push -f origin %s' % branch_name)
       except:
              raise GitPushFailure


def run_deployment_git_commands(branch_name):
       try:
              print("Executing Commands")
              git_delete_branch(branch_name)
              #git_checkout_branch(MASTER_BRANCH)
              #git_pull(MASTER_BRANCH)
              #git_checkout_branch(branch_name)
              #git_push(branch_name)
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


def check_deployment_answer(environment, answer):
       if answer == "yes":
              print_msg("#chamber-of-secrets", "GIT Push approved by "+ data['user_name'])
       elif answer == "no":
              print_msg("#chamber-of-secrets", "GIT Push denied by "+ data['user_name'])
       else:
              print_msg("#chamber-of-secrets", "Invalid command received. Accepted command '/qa_git_push_cmd yes or /qa_git_push_cmd no' ")
'''
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
       return Response(), 200 '''

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
       run_deployment_git_commands('qa')
       #send_scheduled_messages_channel(env_file['scheduled_message'])
       #app.run(port=5000)