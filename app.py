from flask import Flask,redirect,url_for,render_template,request,flash,abort,session
from key import secret_key,salt1,salt2
from stoken import token
from cmail import sendmail
from flask_session import Session
import mysql.connector
import os
from itsdangerous import URLSafeTimedSerializer
app=Flask(__name__)
#hello world
app.secret_key=secret_key
app.config['SESSION_TYPE']='filesystem'
Session(app)
db=os.environ['RDS_DB_NAME']
user=os.environ['RDS_USERNAME']
password=os.environ['RDS_PASSWORD']
host=os.environ['RDS_HOSTNAME']
port=os.environ['RDS_PORT']
with mysql.connector.connect(host=host,user=user,password=password,db=db) as conn:
    cursor=conn.cursor(buffered=True)
    cursor.execute('create table if not exists users(username varchar(50) primary key ,password varchar(50),email varchar(50),email_status enum("confirmed","not confirmed"))')
    cursor.execute('create table if not exists students(roll_no int primary key,name varchar(50),semester int)')
    cursor.execute('create table if not exists subjects(subject_code varchar(50) primary key,subject_name varchar(50))')
    cursor.execute('create table if not exists results(roll_no int,semester int,subject_name varchar(30),subject_code varchar(30),marks int,grade varchar(5))')
mydb=mysql.connector.connect(host=host,user=user,password=password,db=db)
@app.route('/')
def homes():
    return render_template('index.html')

# Results Page
@app.route('/results')
def results():
    return render_template('results.html')

# About Us Page
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/semester_results', methods=['GET','POST'])
def semester_results():
    if request.method == 'POST':
        roll_no = request.form.get('roll_number')
        semester = request.form.get('semester')
        cursor=mydb.cursor()
        query = "SELECT * FROM results WHERE roll_no = %s AND semester=%s"
        values = (roll_no,semester)    
        cursor.execute(query, values)
        results= cursor.fetchall()
        total_marks=0
        for result in results:
            total_marks += result[4]
    
        return render_template('res.html', results=results,total_marks = total_marks)
    return render_template('search.html')

 
@app.route('/log')
def index():
    return render_template('title.html')

@app.route('/login',methods=['GET','POST'])
def login():
    if session.get('user'):
        return redirect(url_for('home'))
    if request.method=='POST':
        username=request.form['username']
        password=request.form['password']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where username=%s',[username])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('select count(*) from users where username=%s and password=%s',[username,password])
            p_count=cursor.fetchone()[0]
            if p_count==1:
                session['user']=username
                cursor.execute('select email_status from users where username=%s',[username])
                status=cursor.fetchone()[0]
                cursor.close()
                if status!='confirmed':
                    return redirect(url_for('inactive'))
                else:
                    return redirect(url_for('home'))
               
            else:
                cursor.close()
                flash('invalid password')
                return render_template('login.html')
        else:
            cursor.close()
            flash('invalid username')
            return render_template('login.html')
    return render_template('login.html')
@app.route('/homepage')
def home():
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        username=session.get('user')
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return render_template('homepage.html')
        else:
            return redirect(url_for('inactive'))
    else:
        return redirect(url_for('login'))
@app.route('/resendconfirmation')
def resend():
    if session.get('user'):
        cursor=mydb.cursor(buffered=True)
        username=session.get('user')
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.execute('select email from users where username=%s',[username])
        email=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flash('Email already confirmed')
            return redirect(url_for('home'))
        else:
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Please confirm your mail-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your mail')
            return redirect(url_for('inactive'))
           
    else:
        return redirect(url_for('login'))

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
         username=request.form['username']
         password=request.form['password']
         email=request.form['email']
         cursor=mydb.cursor(buffered=True)
         try:
            cursor.execute('insert into users(username,password,email)values(%s,%s,%s)',(username,password,email))
         except mysql.connector.IntegrityError:
            flash('Username or email is already used')
            return render_template('registration.html')
         else:
            mydb.commit()
            cursor.close()
            subject='Email Confirmation'
            confirm_link=url_for('confirm',token=token(email,salt1),_external=True)
            body=f"Thanks for singning up. follow this link-\n\n{confirm_link}"
            sendmail(to=email,body=body,subject=subject)
            flash('Confirmation link sent check your mail')
            return render_template('registration.html')
            
    return render_template('registration.html')
@app.route('/inactive')
def inactive():
    if session.get('user'):
        username=session.get('user')
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where username=%s',[username])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            return redirect(url_for('login'))
        else:
            return render_template('inactive.html')
    else:
        return redirect(url_for('login'))

   
@app.route('/confirm/<token>')
def confirm(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt1,max_age=120)
    except Exception as e:
        abort(404,'Link expired')
        #return 'hello'
    else:
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select email_status from users where email=%s',[email])
        status=cursor.fetchone()[0]
        cursor.close()
        if status=='confirmed':
            flah('Email already confirmed')
            return redirect(url_for('login'))
        else:
            cursor=mydb.cursor(buffered=True)
            cursor.execute("update users set email_status='confirmed' where email=%s",[email])
            mydb.commit()
            flash('Email confirmation success')
            return redirect(url_for('login'))
@app.route('/forgot',methods=['GET','POST'])
def forgot():
    if request.method=='POST':
        email=request.form['email']
        cursor=mydb.cursor(buffered=True)
        cursor.execute('select count(*) from users where email=%s',[email])
        count=cursor.fetchone()[0]
        if count==1:
            cursor.execute('Select email_status from users where email=%s',[email])
            status=cursor.fetchone()[0]
            cursor.close()
            if status!='confirmed':
                flash('Please confirm your email first')
                return render_template('forgot.html')
            else:
                subject='Forgot password'
                confirm_link=url_for('reset',token=token(email,salt=salt2),_external=True)
                body=f"Use this link to reset your password-\n\n{confirm_link}"
                sendmail(to=email,body=body,subject=subject)
                flash('Confirmation link sent check your mail')
        else:
            flash('Invalid email id')
            return render_template('forgot.html')
    return render_template('forgot.html')
@app.route('/reset/<token>',methods=['POST','GET'])
def reset(token):
    try:
        serializer=URLSafeTimedSerializer(secret_key)
        email=serializer.loads(token,salt=salt2,max_age=120)
    except:
        abort(404,'link expired')
    else:
        if request.method=='POST':
            newpassword=request.form['npassword']
            confirmpassword=request.form['cpassword']
            if newpassword==confirmpassword:
                cursor=mydb.cursor(buffered=True)
                cursor.execute('update users set password=%s where email=%s',(newpassword,email))
                mydb.commit()
                cursor.close()
                flash('reset succesful')
                return redirect(url_for('login'))      
            else:
                flash('passwords mismatched')
                return render_template('newpassword.html')
        return render_template('newpassword.html')
# Admin Page
@app.route('/admin')
def admin():
    if session.get('user'):
        return render_template('homepage.html')
    else:
        return redirect('/login')



@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        name = request.form['name']
        semester = request.form['semester']
        cursor=mydb.cursor()
        # MySQL Query to insert a new student
        query = "INSERT INTO students (roll_no, name, semester) VALUES (%s, %s, %s)"
        values = (roll_no, name, semester)
        cursor.execute(query, values)
        mydb.commit()
        cursor.close()
        flash("student added succesfully")
        return redirect(url_for('add_student'))
    return render_template('add_student.html')


@app.route('/view_students', methods=['GET', 'POST'])
def view_students():
    cursor = mydb.cursor()
    query = "SELECT * FROM students"
    cursor.execute(query)
    students = cursor.fetchall()
    cursor.close()
    return render_template('view_students.html', students=students)



# Route for adding a subject
@app.route('/add_subject', methods=['GET', 'POST'])
def add_subject():
    if request.method == 'POST':
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        cursor=mydb.cursor()
        query = "INSERT INTO subjects (subject_code, subject_name) VALUES (%s, %s)"
        values = (subject_code, subject_name)
        cursor.execute(query, values)
        mydb.commit()
        cursor.close()
        flash("subject added succesfully")
        return redirect(url_for('add_subject'))    
    return render_template('add_subject.html')

# Route for viewing subjects
@app.route('/view_subjects', methods=['GET', 'POST'])
def view_subjects():
    cursor = mydb.cursor()
    query = "SELECT * FROM subjects"
    cursor.execute(query)
    subjects = cursor.fetchall()
    cursor.close()
    return render_template('view_subjects.html', subjects=subjects)
        

    
@app.route('/add_result', methods=['GET', 'POST'])
def add_result():
    if request.method == 'POST':
        roll_no = request.form.get('roll_no')
        semester = request.form.get('semester')
        subject_name = request.form.get('subject_name')
        subject_code = request.form.get('subject_code')
        marks = request.form.get('marks')
        grade = request.form.get('grade')
        cursor=mydb.cursor()
        query = "INSERT INTO results (roll_no, semester, subject_name,subject_code,marks,grade) VALUES (%s, %s, %s,%s,%s,%s)"
        values = (roll_no, semester, subject_name, subject_code,marks,grade)
        cursor.execute(query, values)
        mydb.commit()
        cursor.close()
        flash("result added succesfully")
        return redirect(url_for('add_result'))
    return render_template('add_result.html')

# Route for viewing results
@app.route('/view_results',methods=['GET','POST'])
def view_results():
    cursor = mydb.cursor()
    query = "SELECT * FROM results"
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return render_template('view_results.html', results=results)
    


@app.route('/logout')
def logout():
    if session.get('user'):
        session.pop('user')
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))


if __name__=='__main__':
    app.run()



