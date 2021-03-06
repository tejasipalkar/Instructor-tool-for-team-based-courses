
from flask import render_template, url_for, json, flash, redirect, request, jsonify, session
from instructorTool import app
from instructorTool.forms import LoginForm
from instructorTool.Canvas_Scripts.course import Course
from instructorTool.Canvas_Scripts.canvas_calendar import Canvas_Calendar
from instructorTool.Canvas_Scripts.canvas_group import Canvas_Group
from instructorTool.Canvas_Scripts.stg_grouping import STG_Group
from instructorTool.Canvas_Scripts.github import Github
from instructorTool.LaTex import Assign_tex
from instructorTool.models import User, Configuration, courseObj
from instructorTool import db, login_manager
from flask_login import login_user, current_user, logout_user, login_required
from instructorTool.Group_Scripts.group_online import OnlineGroup
from instructorTool.Group_Scripts.fetch import FetchInfo
from instructorTool.Group_Scripts.fetch_campus import FetchCampusInfo
from instructorTool.Group_Scripts.save_csv import save_csv
import jwt, requests, base64, csv, traceback, sys, os, flask
import pandas as pd

canvas_calendar = ''
sys.stdout = sys.stderr = open('instructor_log.txt','wt')
@app.route("/")
@app.route("/login")
def login():
    logout_user()
    if 'canvas_token' in session:
        session.pop('canvas_token', None)
    if 'course_id' in session:
        session.pop('course_id', None)
    if 'tableData' in session:
        session.pop('tableData', None)
    return render_template('login.html',title ="Login")

@app.route("/home", methods=['POST', 'GET'])
@login_required
def home():
    if request.method == 'POST':
        token = request.form['token']
        canvas = Course(token)
        try:
            course_names=canvas.getcourse()
        except:
            error = "Token Not Valid. Please Enter the Correct Token"
            return render_template('token.html', error = error)
        session['canvas_token'] = token
    else:
        if 'canvas_token' not in session:
            return render_template('token.html')
        token = session['canvas_token']
        canvas = Course(token)
        course_names=canvas.getcourse()
    courseList = []
    for course in course_names:
        courseobj = courseObj()
        courseobj.id = course
        courseobj.name = ""
        courseobj.full_name = course
        fullName = course.split(':')
        if len(fullName) > 1 :
            courseobj.id = fullName[0]
            courseobj.name = fullName[1]
        courseList.append(courseobj)
    return render_template('home.html',title ="Home",courses=courseList)

@app.route("/about")
@login_required
def about():
    return render_template('about.html')

@app.route("/group")
@login_required
def group():
    doc_url = request.args.get('file')
    pref = request.args.get('pref')
    avoid = request.args.get('avoid')
    group_size = request.args.get('group')
    input_select = request.args.get('input_select')
    if doc_url and pref and avoid:
        return fetch_document(doc_url, pref, avoid, group_size, input_select)
    return render_template('group_page.html',title="Manage Groups")

@app.route("/submitgroups", methods = ['POST'])
@login_required
def submitgroups():
    newvalues = request.json['new']
    items = request.json['items']
    table = request.json['actualTable']
    # Call save table
    save_tbl = save_csv(table)
    save_tbl.save()
    newDict ={}
    for item in items:
        for value in newvalues:
            if(item['Group'] == value['GroupNumber']):
                item['Group'] = value['GroupName']

    for tableitem in table:
        for value in newvalues:
            if(tableitem['GroupName'] == value['GroupNumber']):
                tableitem['GroupName'] = value['GroupName']

    session['tableData'] = tableitem
    session['new'] = newvalues
    session['table'] = table
    for item in items:
        if item['Group'] not in newDict:
            newDict[item['Group']] = [item['EmailID']]
        else:
            newDict[item['Group']].append(item['EmailID'])

    groupObject = Canvas_Group(session['canvas_token'])
    result = groupObject.create_groups(newDict, session['course_id'])
    return flask.jsonify(result)


@app.route("/cal")
@login_required
def cal():
    if 'canvas_token' in session:
        if 'course_id' in session:
            course_id = session['course_id']
            global canvas_calendar
            token = session['canvas_token']
            canvas_calendar = Canvas_Calendar(token)
            result = canvas_calendar.getallevents(str(course_id))
            myevents = json.dumps(result['events'])
            assignments = json.dumps(result['assignments'])
            return render_template('calendar.html', events = myevents, assignments = assignments, course= "course_"+str(course_id))
        else:
            flash('Select a course to access calendar!','danger')
            return redirect(url_for('home'))
    else:
        flash('Session expired!','danger')
        return redirect(url_for('login'))

@app.route("/newevent", methods=['POST'])
@login_required
def newEvents():
    response = request.data
    responseObj = json.loads(response)
    result = canvas_calendar.create_event(responseObj)
    return result

@app.route("/editevent", methods=['POST'])
@login_required
def editEvents():
    response = request.data
    responseObj = json.loads(response)
    result = canvas_calendar.edit_event(responseObj)
    return result

@app.route("/deleteevent", methods=['POST'])
@login_required
def deleteEvents():
    response = request.data
    responseObj = json.loads(response)
    result = canvas_calendar.delete_event(responseObj)
    return result

@app.route("/editassign", methods=['POST'])
def editAssign():
    response = request.data
    responseObj = json.loads(response)
    result = canvas_calendar.edit_assignment(responseObj['event'], responseObj['course'].split("_")[1])
    return result

@app.route("/latexproject", methods=['POST'])
def latexProject():
    response = request.data
    responseObj = json.loads(response)
    result = Assign_tex.myfun(responseObj)
    return result

@app.route("/latexassign", methods=['POST'])
def latexAssign():
    response = request.data
    responseObj = json.loads(response)
    result = Assign_tex.myassign(responseObj)
    return result

@app.route('/send', methods=['GET','POST'])
@login_required
def send():
    course_name = request.args.get('course_name')
    if course_name:
        token = session['canvas_token']
        canvas = Course(token)
        course_names=canvas.getcourse()
        for key, value in course_names.items():
            if key == course_name:
                course_id = value
        session['course_id'] = course_id
        return render_template('course_page.html',title = "Course Page", course= course_name)

    return render_template('home.html')


@app.route("/logout")
def logout():
    session.pop('canvas_token', None)
    session.pop('course_id', None)
    session.pop('tableData', None)
    logout_user()
    return redirect(url_for('login'))

@app.route("/account")
@login_required
def account():
    return render_template('account.html')

@app.route("/slack", methods = ['POST'])
@login_required
def slack():
    slack_token = request.form.get('slack_token')
    canvas_token = session['canvas_token']
    course_id = session['course_id']
    slack = STG_Group(canvas_token)
    result = slack.create_slack_groups(slack_token, course_id)
    if result == "invalid_auth":
        return 'invalid token'
    return 'done'

@app.route("/taiga", methods = ['POST'])
@login_required
def taiga():
    taiga_username = request.form.get('username')
    taiga_password = request.form.get('password')
    taiga_desc = request.form.get('description')
    canvas_token = session['canvas_token']
    course_id = session['course_id']
    taiga = STG_Group(canvas_token)
    result = taiga.create_taiga_channels(taiga_username, taiga_password, taiga_desc, course_id)
    if result == 'invalid auth':
        return result
    return 'done'

@app.route("/github", methods = ['POST'])
@login_required
def github():
    github_token = request.form.get('github_token')
    repo_owner = request.form.get('repo_owner')
    canvas_token = session['canvas_token']
    course_id = session['course_id']
    github = STG_Group(canvas_token)
    result = github.get_groupsdata(course_id)
    group_data = {}
    try:
        table = session['table']
        for tableitem in table:
            if tableitem['GroupName'] in group_data:
                group_data[tableitem['GroupName']].append(tableitem['Github'])
            else:
                group_data[tableitem['GroupName']] = []
                group_data[tableitem['GroupName']].append(tableitem['Github'])


        new_group_data = {}
        for elements in session['new']:
            new_group_data[elements['GroupName']] = group_data[elements['GroupName']]

        for key in new_group_data.keys():
            g = Github(repo_owner, github_token)
            response = g.create_github_repo(key)
            result = response.status_code
            if(result != 201):
                return 'invalid token'

            print("####key####")
            print(key)
            os.system("sh /home/ec2-user/newbuild/SER_517_Software_Factory_group5/instructorTool/test_unix.sh {0} {1} {2} ".format(github_token, repo_owner, key))
            for val in new_group_data[key]:
                print("####github_IDs####")
                print(val)
                g.add_collaborator(key, val)
    except:
        traceback.print_exc(file=sys.stdout)
        return 'invalid token' 
    return 'done'

@login_required
def fetch_document(doc_id, pref, avoid, group_size, input_select):
    if input_select == 'Online':
        f = FetchInfo(doc_id, pref, avoid, group_size)
    else:
        f = FetchCampusInfo(doc_id, pref, avoid, group_size)
    res = f.fetch_document()
    session['response'] = res.to_json(orient='split')
    return res.to_json(orient='split')

@app.route("/oauthcallback")
def callback():
    code = request.args.get('code')
    client_id = Configuration.query.filter_by(key="oauth_client_id").first().value
    client_secret = Configuration.query.filter_by(key="oauth_client_secret").first().value
    redirect_uri = getConfig("aws_redirect_uri", "http://127.0.0.1:5000/oauthcallback")
    PARAMS = {'code':code, 'client_id': client_id,
    'client_secret': client_secret, 'redirect_uri': redirect_uri,
    'grant_type': 'authorization_code'}
    URL = "https://oauth2.googleapis.com/token"
    # sending get request and saving the response as response object
    r = requests.post(url = URL, data = PARAMS)
    # extracting data in json format
    data = r.json()
    segments = data['id_token'].split('.')

    if (len(segments) != 3):
        raise Exception('Wrong number of segments in token: %s' % id_token)

    b64string = segments[1]
    padding =  '=' * (4 - len(b64string) % 4)
    padded = str(b64string) + str(padding)
    response = base64.b64decode(padded)
    response = str(response, 'utf-8')
    res = json.loads(response)
    email = res['email']
    domain = email.split('@')[1]
    whitelisted_email = Configuration.query.filter_by(key="email.whitelist").first()
    if domain != "asu.edu" and email != whitelisted_email:
        return "Please login via asu.edu account"
    name = res['name']
    user = User.query.filter_by(email=email).first()
    if user:
        login_user(user)
    else:
        user = User(name, email)
        db.session.add(user)
        db.session.commit()
        login_user(user)
    access_token = data['access_token']
    access_token = "Bearer " + access_token
    session['access_token'] = access_token
    return redirect(url_for('token'))

@app.route("/google")
def sendrequest():
    client_id = Configuration.query.filter_by(key="oauth_client_id").first().value
    redirect_uri = getConfig("aws_redirect_uri", "http://127.0.0.1:5000/oauthcallback")
    url = "https://accounts.google.com/o/oauth2/auth?response_type=code&client_id="\
    + str(client_id)\
    +"&scope=https://www.googleapis.com/auth/drive+email+profile&redirect_uri="\
    + redirect_uri
    return redirect(url)

@app.route("/initconfig")
def initdatabase():
    return render_template('initconfig.html')

def getConfig(config_name, default):
    config = Configuration.query.filter_by(key=config_name).first()
    if config:
        return config.value
    else:
        return default

@app.route("/addconfig")
def addconfig():
    name = request.args.get('name')
    value = request.args.get('value')
    config = Configuration.query.filter_by(key=name).first()
    if config:
        config.value = value
        db.session.flush()
        db.session.commit()
        return ("Configuration updated successfully")
    else:
        config = Configuration(name, value)
        db.session.add(config)
        db.session.commit()
    return ("Configuration added successfully")

@app.route("/token")
@login_required
def token():
   return render_template('token.html')


