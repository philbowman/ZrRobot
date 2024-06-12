from flask import Flask, render_template, request, abort, flash, redirect, url_for, g, session, send_from_directory
import os

from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


from sqlalchemy.orm import scoped_session
from puller import Submit50
from puller_gc import *
# import greenlet
from puller_ps import list_section_events, make_ps_roster
from secrets_parameters import *
from flask_migrate import Migrate
from models import *

# Initialize Flask app
app = Flask(__name__)


# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URL
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.debug = True
db.init_app(app)
migrate = Migrate(app, db)
with app.app_context():
    db.create_all()

app.secret_key = flask_secret_key
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
GOOGLE_CLIENT_ID = oauth_clientid


@login_manager.user_loader
def load_user(user_id):
    # Implement a user loading function (e.g., from a database)
    return User.get(user_id)

@app.route('/login')
def login():
    return render_template('login.j2', google_clientid=oauth_clientid)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login', google_clientid=oauth_clientid))

@app.route('/login/callback', methods=['POST'])
def verify_id_token(id_token_string=None):
    if not id_token_string:
        abort(500)
    idinfo = id_token.verify_oauth2_token(
        id_token_string, requests.Request(), oauth_clientid)
    # Verify that the 'iss' (issuer) is correct.
    if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
        raise ValueError('Wrong issuer.')
    current_user.email = idinfo['email']

    # You can now access user information, such as idinfo['sub'] and idinfo['email'].
    # Create or authenticate the user in your Flask app as needed.

    return redirect(url_for('main_page'))

# @app.route('/login/callback', methods=['POST'])
# def login_callback():
#     id_token_string = request.form['idtoken']
#     idinfo = id_token.verify_oauth2_token(id_token_string, google_requests.Request(), GOOGLE_CLIENT_ID)
#     if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
#         raise ValueError('Wrong issuer.')
#     user = User(idinfo['sub'], idinfo['email'])
#     login_user(user)
#     return redirect(url_for('main_page'))


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


# Initialize a scoped session to ensure that each HTTP request has its own session 
# which is based on the greenlet's current identifier.
# Session = scoped_session(SessionLocal, scopefunc=greenlet.getcurrent)

# Define constants
STUDENTWORK_DIR = "studentwork"
COMPARE50_DIR = "compare50"  
COURSE_ID = 1872
TOKEN = '25e0c040383247d6a9e3d2ca9c54d4e6'  

comfort_levels = [member.name.lower() for member in ComfortLevel]

requirement_types = [member.name.lower() for member in RequirementType]

@app.route('/section/<int:section_id>/pull_roster')
def update_section_roster(section_id):
    # db.session = Session()
    section = db.session.query(Section).filter_by(id=section_id).first()
    make_ps_roster(db.session, section)
    flash('Updated section roster!', 'success')
    return redirect(request.referrer)

@app.route('/set_autopull')
def set_autopull():
    session['autopull'] = not session.get('autopull', False)
    return redirect(request.referrer)


@app.route('/set_term', methods=['POST'])
def set_term():
    selected_term = request.form.get('term')
    # Set session['term'] to the selected term
    try:
        session['termid'] = int(selected_term)
    except ValueError:
        session['termid'] = None
    # Redirect back to the referring page (the page where the form was submitted)
    return redirect(request.referrer)

def refresh_data(kind, course=None):
    # db.session = Session()
    if kind == 'all':
        kinds = ['gc', 'ps', 'cs50']
    else:
        kinds = [kind]
    if 'ps' in kinds:
        schools = {hs_schoolid: "HS"}
        try:
            section_events, bell_schedules, day_schedules = list_section_events(db.session, schools, False)
        except KeyError:
            section_events, bell_schedules, day_schedules = list_section_events(db.session, schools, True)
            
        for section in db.session.query(Section).filter_by(teacher_email=session['user_email']).all():
            make_ps_roster(db.session, section)
        flash('Refreshed PowerSchool Data!', 'success')
    if 'gc' in kinds:
        pull_gc(db.session, session['user_email'])
        update_course_students()
        session['courses'] = None
        load_courses()
        flash('Refreshed Google Classroom Data!', 'success')
    if 'cs50' in kinds:
        if course:
            courses = [course]
        else:
            # query students who have a username
            courses = db.session.query(Course).filter(Course.cs50_course_id != None).all()

        for c in courses:
            cs50data = Submit50(c.cs50_course_id, TOKEN, STUDENTWORK_DIR)
            for student in c.students:
                cs50data.add_student({'email': student.email, 'name': student.name, 'username': student.username})
            cs50data.refresh_data(pull=False, compare=False)
            cs50data.write_student_csv()
            cs50data.write_to_db(db.session)
            flash('Refreshed CS50 Data!', 'success')

@app.route('/refresh/all')
def refresh_all():
    refresh_data('all')
    return redirect(url_for('main_page'))

def cleanup_db():
    for course in db.session.query(Course).filter_by(gid=None).all():
        logger.info(f"Deleting course {course.id}")
        db.session.delete(course)
    for coursework in db.session.query(CourseWork).filter_by(gid=None).all():
        logger.info(f"Deleting coursework {coursework.id}")
        if coursework.course:
            coursework.course = None
        db.session.delete(coursework)
    for submission in db.session.query(Submission).filter_by(gid=None).all():
        logger.info(f"Deleting submission {submission.id}")
        submission.coursework = None
        db.session.delete(submission)

@app.route('/course/<int:course_id>/set_cs50_course', methods=["POST"])
def set_cs50_course(course_id):
    course = db.session.query(Course).filter_by(id=course_id).first()
    course.cs50_course_id = request.form.get('cs50_course_id')
    db.session.commit()
    return redirect(request.referrer)

@app.route('/refresh/gc')
def refresh_gc():
    cleanup_db()
    refresh_data('gc')
    return redirect(url_for('courses_page'))

@app.route('/refresh/ps')
def refresh_ps():
    refresh_data('ps')
    return redirect(url_for('sections_page'))

@app.route('/refresh/cs50')
def refresh_cs50():
    refresh_data('cs50')
    return redirect(url_for('main_page'))

@app.route('/sections')
def sections_page():
    # db.session = Session()
    # Fetch all sections
    sections = db.session.query(Section).filter_by(teacher_email=session['user_email']).all()
    courses = db.session.query(Course).all()

    return render_template('sections.j2', sections=sections, courses=courses)

@app.route('/course/<int:course_id>/pull/<int:courseworks>/<int:submissions>')
def course_pull(course_id, courseworks=False, submissions=False):
    course = db.session.query(Course).filter_by(id=course_id).first()
    if course:
        add_course(db.session, course=course)
        if courseworks:
            cwlist = list_coursework(db.session, course=course)
        if submissions:
            for cw in cwlist:
                list_submissions(db.session, cw)
    if request.endpoint == 'course_pull':
        return redirect(request.referrer)
    return course

@app.route('/topic/<int:topic_id>/<int:grade_assignments>/<int:assigned_grade>')
def topic_grade(topic_id, grade_assignments=False, assigned_grade=False):
    topic = db.session.query(Topic).filter_by(id=topic_id).first()
    if not topic:
        flash('Topic not found!', 'error')
        return redirect(request.referrer)
    
    overall_cw = CourseWork.from_topic(topic)

    if grade_assignments:
        for cw in topic.courseworks:
            if cw == overall_cw:
                continue
            coursework_grade(cw.id, assigned_grade=assigned_grade)
    coursework_grade(overall_cw.id, assigned_grade=assigned_grade)
    return redirect(request.referrer)

@app.route('/topic/<int:topic_id>')
@app.route('/notopic/<int:course_id>')
def topic_page(topic_id=None, course_id=None):
    if topic_id:
        topic = db.session.query(Topic).filter_by(id=topic_id).first()
    else:
        topic = None
    if course_id:
        course = db.session.query(Course).filter_by(id=course_id).first()
    else:
        course = None
    
    if not topic and not course:
        flash('Topic not found!', 'error')
        return redirect(request.referrer)
    
    if not topic:
        topic = Topic(name="No Topic", id=None, course=course, courseworks = [cw for cw in db.session.query(CourseWork).filter_by(course_id=course_id).filter_by(topic_id=None).all()])
    return render_template('topic.j2', topic=topic)

@app.route('/topic/overall/<int:topic_id>')
def make_topic_overall(topic_id=None):
    topic = db.session.query(Topic).filter_by(id=topic_id).first()
    cw = CourseWork.from_topic(topic)
    if cw.gid:
        patch_coursework(db.session, cw)
    else:
        create_coursework(db.session, cw)
    return redirect(url_for('topic_page', topic_id=topic.id))

@app.route('/course/gradebook/<int:course_id>')
def gradebook_page(course_id=None):
    course = db.session.query(Course).filter_by(id=course_id).first()
    if not course:
        flash('Course not found!', 'error')
        return redirect(request.referrer)
    gradebook_cw = course.make_gradebook()

    if not gradebook_cw.gid:
        create_coursework(db.session, gradebook_cw)
    else:
        patch_coursework(db.session, gradebook_cw)
    
    return redirect(url_for('coursework_page', coursework_id=gradebook_cw.id))


@app.route('/course/<int:course_id>', methods=['GET', 'POST'])
def course_page(course_id, pull=False):
    # db.session = Session()
    # Fetch course
    if pull or session.get('autopull'):
        course = course_pull(course_id, 1, 0)
    else:
        course = db.session.query(Course).filter_by(id=course_id).first()
    
    if not course:
        flash(f'Course (id={course_id}) not found!', 'error')
        return redirect(url_for('courses_page'))

    sections = db.session.query(Section).filter_by(course_id=course_id).all()
    # Fetch all students in the section
    # students = db.session.query(Student).filter_by(section_id=section_id).all()

    if request.method == 'POST':
        courseworks = request.form.getlist('coursework_id')
        topics = request.form.getlist('topic')
        for cwid, topicid in zip(courseworks, topics):
            coursework = db.session.query(CourseWork).filter_by(id=int(cwid)).first()
            if coursework:
                tid = int0(topicid) or None
                if coursework.topic_id != tid:
                    coursework.topic_id = tid
                    db.session.commit()
                    db.session.flush()
                    coursework = patch_coursework(db.session, coursework)
    return render_template('course.j2', course=course, sections=sections)

@app.route('/courses')
def courses_page():
    # db.session = Session()
    # Fetch all courses
    courses = db.session.query(Course).all()
    return render_template('courses.j2', courses=courses)

# Main route to display all students and problems
@app.route('/')
@login_required
def main_page():
    issues = db.session.query(Issue).all()
    return render_template('main.j2', issues=issues)

@app.route('/section/<int:section_id>', methods=['GET', 'POST'])
def section_page(section_id):
    # db.session = Session()
    # Fetch section
    section = db.session.query(Section).filter_by(id=section_id).first()
    courses = db.session.query(Course).all()
    # Fetch all students in the section
    # students = db.session.query(Student).filter_by(section_id=section_id).all()

    if request.method == 'POST':
        if not request.form['course']:
            section.course = None
        
        course = db.session.query(Course).filter_by(id=request.form['course']).first()
        section.course = course
        db.session.commit()
        course.descriptionHeading = ','.join([str(s.ps_dcid) for s in course.sections])
        course.section_desc = course.terms()
        payload = make_payload(course, ['descriptionHeading', 'section_desc'])
        push_update(db.session, course, payload)
        session['courses'] = None
        load_courses()
        flash('Updated section!', 'success')
        return redirect(url_for('sections_page'))


    return render_template('section.j2', section=section, courses=courses)



@app.route('/problem/edit/new', methods=['GET', 'POST'])
@app.route('/problem/edit/<int:problem_id>', methods=['GET', 'POST'])
def create_or_edit_problem(problem_id=None):
    # db.session = Session()
    problem = None

    if problem_id:
        problem = db.session.query(Problem).filter_by(id=problem_id).first()
        if not problem:
            flash('Problem not found!', 'error')
            return redirect(url_for('problems_page'))

    if request.method == 'POST':

        if not problem:
            problem = Problem()

        problem.title = request.form['title']
        problem.slug = request.form['slug']
        problem.foldername = Submit50.make_foldername(problem.slug)
        problem.url = request.form['url']
        problem.autograder = request.form['autograder']
        problem.allow_delete = 1
        problem.avg_method = request.form['avg_method']
        if request.form.get('manual_criteria'):
            problem.autograder = "manual"
            mc_sequences = request.form.getlist('mc_sequence')
            mc_titles = request.form.getlist('mc_title')
            mc_descriptions = request.form.getlist('mc_description')
            mc_points = request.form.getlist('mc_max_points')
            mc_categories = request.form.getlist('mc_categories_list')

            db.session.commit()
            desired_criteria = []

            for sequence, title, description, points, category in zip(mc_sequences, mc_titles, mc_descriptions, mc_points, mc_categories):
                mc = Criterion(sequence=int(sequence), grading_categories=category, title=title, description=description, max_points=int(points or 1))
                db.session.add(mc)
                desired_criteria.append(mc)

            problem.criteria = desired_criteria

        if not problem_id:
            db.session.add(problem)

        db.session.commit()
        flash(f"{'Updated' if problem_id else 'Created'} problem successfully!", 'success')
        return redirect(url_for('create_or_edit_problem', problem_id=problem.id))

    return render_template(
        'edit_problem.j2',
        problem=problem,
        grading_categories = ["ENGAGEMENT", "PROCESS", "PRODUCT", "EXPERTISE"]
    )

@app.route('/problem/delete/<int:problem_id>')
def delete_problem(problem_id=None):
    # db.session = Session()
    if problem_id:
        problem = db.session.query(Problem).filter_by(id=problem_id).first()
        if not problem:
            flash('Problem not found!', 'error')
            return redirect(url_for('problems_page'))
        if not problem.allow_delete:
            flash('Problem should not be deleted!', 'error')
            # return redirect(url_for('problems_page'))
        db.session.delete(problem)
        db.session.commit()
        flash('Problem deleted successfully!', 'success')
    return redirect(url_for('problems_page'))

@app.route('/problemset/delete/<int:problemset_id>')
def delete_problemset(problemset_id=None):
    # db.session = Session()
    if problemset_id:
        problemset = db.session.query(ProblemSet).filter_by(id=problemset_id).first()
        if not problemset:
            flash('Problemset not found!', 'error')
            return redirect(url_for('problemsets_page'))
        db.session.delete(problemset)
        db.session.commit()
        flash('Problemset deleted successfully!', 'success')
    return redirect(url_for('problemsets_page'))

@app.route('/problemset/create_or_edit', methods=['GET', 'POST'])
@app.route('/problemset/edit/<string:problemset_id>', methods=['GET', 'POST'])
def create_or_edit_problemset(problemset_id=None):
    
    if problemset_id:
        problemset = db.session.query(ProblemSet).filter_by(id=problemset_id).first()
        if not problemset:
            flash('Problemset not found!', 'error')
            return redirect(url_for('problemsets_page'))
        ps_items = problemset.adjust_item_sequence()

    else:
        problemset = ProblemSet()
        db.session.add(problemset)
        ps_items = []
        
    if request.method == 'POST':
        title = request.form['title']
        selected_problems = request.form.getlist('problems')  # Get selected problem IDs as a list
        number_required = request.form['number_required']
        comforts = request.form.getlist('comfort_levels')
        requirements = request.form.getlist('requirement_types')
        sequences = request.form.getlist('sequence')
        problemset.num_required = int(number_required)

        problemset.title = title
        if problemset.topic_overall:
            CourseWork.from_topic(problemset.topic_overall[0].topic[0])

        new_items = []

        # Associate selected problems with the problemset
        for problem_id, comfort, req_type, sequence in zip(selected_problems, comforts, requirements, sequences):
            # Ensure problem_id is an integer
            problem_id_int = int(problem_id[problem_id.find('-')+1:])
            if problem_id.startswith('prob-'):
                item = db.session.query(ProblemSetItem).filter_by(problemset_id=problemset.id, problem_id=problem_id_int).first()
                newitem = ProblemSetItem(problem_id=problem_id_int, comfort_level=comfort, requirement_type=req_type, sequence=int(sequence))
            elif problem_id.startswith('ps-'):
                item = db.session.query(ProblemSetItem).filter_by(problemset_id=problemset.id, nested_problemset_id=problem_id_int).first()
                newitem = ProblemSetItem(nested_problemset_id=problem_id_int, comfort_level=comfort, requirement_type=req_type, sequence=int(sequence))
            elif problem_id.startswith('cw-'):
                cw = db.session.query(CourseWork).filter_by(id=problem_id_int).first()
                newitem = None
                item = ProblemSetItem.from_coursework(problemset, cw)
            if newitem and not item:
                db.session.add(newitem)
                new_items.append(newitem)
            elif item:
                item.comfort_level = comfort
                item.requirement_type = req_type
                item.sequence = int(sequence)
                new_items.append(item)

        db.session.commit()

        problemset.items = [it for it in new_items]
        problemset.adjust_num_required()
        db.session.commit()

        ps_items = problemset.adjust_item_sequence()

        flash(f"{'Updated' if problemset_id else 'Created'} problemset successfully!", 'success')
        # return redirect(url_for('create_or_edit_problemset', problemset_id=problemset.id))

    problems = db.session.query(Problem).all()
    problem_sets = db.session.query(ProblemSet).all()
    courseworks = [i.nested_coursework for i in problemset.items if i.nested_coursework]
    # if problemset.topic_overall:
        # courseworks = db.session.query(CourseWork).filter_by(course=problemset.topic_overall[0].course()).all()

    return render_template(
        'edit_problemset.j2',
        courseworks=courseworks,
        problemset=problemset,
        ps_items = ps_items,
        problems=problems,
        problem_sets=problem_sets,
        comfort_levels=comfort_levels,
        requirement_types=requirement_types
    )



@app.route('/problemsets/')
def problemsets_page():
    # db.session = Session()
    # Retrieve all problem sets
    problemsets = db.session.query(ProblemSet).all()
    return render_template('problemsets.j2', problemsets=   problemsets)



@app.route('/user/int:<studentid>')
def user_page(studentid):
    # db.session = Session()
    # Get the student from the database
    student = db.session.get(Student, int(studentid))

    # Return a 404 error if the student is not found
    if not student:
        abort(404)

    # Get all submissions for the student
    submissions = db.session.query(ProblemSubmission).filter_by(student_id=student.id).all()

    return render_template('user.j2', student=student, submissions=submissions)


@app.route('/coursework/new', methods=['GET', 'POST'])
@app.route('/coursework/new/<int:course_id>', methods=['GET', 'POST'])
@app.route('/coursework/<int:coursework_id>', methods=['GET', 'POST'])
def coursework_page(coursework_id=None, course_id=None):
    coursework = None
    courses = db.session.query(Course).all()
    problemsets = db.session.query(ProblemSet).all()
    if coursework_id:
        coursework = db.session.query(CourseWork).filter_by(id=coursework_id).first()
        if not coursework:
            flash('Coursework not found!', 'error')
            return redirect(url_for('courseworks_page'))
    else:
        if course_id:
            course = db.session.query(Course).filter_by(id=course_id).first()
            if not course:
                flash('Course not found!', 'error')
            coursework = CourseWork(course=course)
        else:
            coursework = CourseWork()

    if request.method == 'POST':
        # if not coursework:
        #     coursework = CourseWork()

        problemset_id = request.form['problemset']
        for req in coursework.problemsets:
            coursework.problemsets.remove(req)
            db.session.commit()
            db.session.flush()

        
        if problemset_id:
            problemset = db.session.query(ProblemSet).filter_by(id=problemset_id).first()
            if not problemset:
                flash('Problemset not found!', 'error')
                return redirect(request.referrer)
            coursework.problemsets.append(problemset)
        
        course_id = request.form['course']
        course = db.session.query(Course).filter_by(id=course_id).first()

        if not course:
            flash('Course not found!', 'error')
            return redirect(request.referrer)
        coursework.course = course
        coursework.title = request.form['title']
        coursework.description = request.form['description']
        if request.form.get('topic'):
            topic = db.session.query(Topic).filter_by(id=int(request.form['topic'])).first()
            if topic:
                coursework.topic_id = topic.id
                coursework.topicId = topic.gid
            else:
                coursework.topic_id = None
                coursework.topicId = None
        else:
            coursework.topic_id = None
            coursework.topicId = None
        attachment_urls = [u for u in request.form.getlist('attachments[]') if u]
        coursework.dueDateTime = GAPI_Date(request.form.get('dueDateTime') or None)
        coursework.scheduledTime = GAPI_Date(request.form.get('scheduledTime') or None)
        coursework.maxPoints = int(request.form.get('maxPoints') or 0)
        if not request.form.get('draft'):
            coursework.state = coursework.state = "PUBLISHED"
        else:
            coursework.state = coursework.state = "DRAFT"
        if not coursework_id:
            db.session.add(coursework)

        for attachment in coursework.attachments:
            if attachment.url in attachment_urls:
                attachment_urls.remove(attachment.url)
            else:
                coursework.attachments.remove(attachment)
                db.session.commit()
                db.session.flush()
        for url in attachment_urls:
            attachment = Attachment(url=url)
            db.session.add(attachment)
            coursework.attachments.append(attachment)



        db.session.commit()
        db.session.flush()
        if not coursework.gid:
            coursework = create_coursework(db.session, coursework)
        else:
            coursework = patch_coursework(db.session, coursework)
        flash(f"{'Updated' if coursework_id else 'Created'} coursework successfully!", 'success')

    return render_template(
        'coursework.j2',
        coursework=coursework,
        courses=courses,
        problemsets=problemsets
    )

@app.route('/coursework/<int:coursework_id>/pull')
def coursework_pull(coursework_id):
    coursework = db.session.query(CourseWork).filter_by(id=coursework_id).first()
    coursework = add_coursework(db.session, coursework=coursework)
    return redirect(url_for('coursework_page', coursework_id=coursework.id))

# @app.route('/coursework/<int:coursework_id>')
# def coursework_page(coursework_id):
#     # db.session = Session()
#     # Get the coursework from the database
#     coursework = db.session.get(CourseWork, coursework_id)
#     problemsets = db.session.query(ProblemSet).all()

#     # Return a 404 error if the coursework is not found
#     if not coursework:
#         abort(404)

#     return render_template('coursework.j2', coursework=coursework, problemsets=problemsets)

@app.route('/coursework/<int:coursework_id>/copy/<int:draft>')
def make_coursework_copy(coursework_id, draft):
    # Get the coursework from the database
    coursework = db.session.get(CourseWork, coursework_id)
    # Return a 404 error if the coursework is not found
    if not coursework:
        abort(404)
    new_coursework = copy_coursework(db.session, coursework, not bool(draft), bool(draft))
    for problemset in coursework.problemsets:
        new_coursework.problemsets.append(problemset)
    
    flash('Copied coursework!', 'success')
    return redirect(url_for('coursework_page', coursework_id=new_coursework.id))

@app.route('/submission/<int:submission_id>')
def submission_page( submission_id):
    submission = db.session.get(Submission, submission_id)
    rubric = submission.get_rubric()
    if submission.coursework.problemsets:
        try:
            manual_input_problems = submission.coursework.problemsets[0].manual_input_problems(rubric=rubric)
        except KeyError:
            manual_input_problems = submission.coursework.problemsets[0].manual_input_problems(rubric=None)
    else:
        manual_input_problems = []
    
    return render_template('submission.j2', manual_input_problems=manual_input_problems, submission=submission, rubric=rubric.total_scores(), grade=None)

@app.route('/submission/<int:submission_id>/pull')
def submission_pull(submission_id):
    submission = db.session.get(Submission, submission_id)
    add_submission(db.session, submission=submission)
    flash(f'Pulled GC data for {submission.get_title()}!', 'success')
    return redirect(url_for('submission_page', submission_id=submission.id))    

@app.route('/submissions/<int:coursework_id>/pull')
def submissions_pull(coursework_id):
    coursework = db.session.get(CourseWork, coursework_id)
    add_coursework(db.session, coursework=coursework)
    list_submissions(db.session, coursework)
    flash(f'Pulled GC data for {coursework.title}!', 'success')
    return redirect(url_for('coursework_page', coursework_id=coursework.id))

@app.route('/coursework/<int:coursework_id>/grade/<int:assigned_grade>')
def coursework_grade(coursework_id, assigned_grade=False, rubric_doc=True, post_only=False):
    # db.session = Session()
    coursework = db.session.get(CourseWork, coursework_id)
    if not coursework.problemsets:
        flash('No problemsets associated with this coursework!', 'error')
        return redirect(request.referrer)
    for submission in coursework.submissions:   
        submission_grade(submission.id, assigned_grade)
    if request.endpoint == 'coursework_grade':
        return redirect(request.referrer)
    return coursework

@app.route('/coursework/post_grades/<int:coursework_id>')
def coursework_post_grades(coursework_id):
    # db.session = Session()
    coursework = db.session.get(CourseWork, coursework_id)
    for submission in coursework.submissions:
        submission_post_grade(submission.id)
    return redirect(request.referrer)

@app.route('/submission/post_grade/<int:submission_id>')
def submission_post_grade(submission_id):
    submission = db.session.get(Submission, submission_id)
    submission.update_score(assigned_grade=True)
    patch_submission(db.session, submission.coursework, submission)
    if request.endpoint == 'submission_post_grade':
        return redirect(request.referrer)
    return submission

@app.route('/submission/clear_rubric/<int:submission_id>')
def submission_clear_rubric(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        flash('Submission not found!', 'error')
    else:
        submission.rubric = None
        db.session.commit()
        db.session.flush()
    
    return redirect(request.referrer)
    
@app.route('/submission/<int:submission_id>/grade/<int:assigned_grade>/<int:post_only>/<int:rubric_doc>')
def submission_grade(submission_id, assigned_grade=False, post_only=False, rubric_doc=True, force=False):
    submission = db.session.get(Submission, submission_id)
    if not submission.coursework.problemsets:
        flash('No problemsets associated with this coursework!', 'error')
        return redirect(request.referrer)
    try:
        rubric = submission.grade(force=force)
    except Exception:
        if not force:
            rubric = submission.grade(force=True)
    if rubric_doc:
        make_rubric_doc(db.session, submission)
    submission.update_score(assigned_grade=bool(assigned_grade))
    try:
        patch_submission(db.session, submission.coursework, submission)
    except Exception as e:
        if "404" in str(e):
            flash('Submission not found!', 'error')
    if request.endpoint == 'submission_grade':
        return redirect(request.referrer)
    return submission

@app.route('/submission/<int:submission_id>/grade_manual', methods=['POST'])
def submission_grade_manual(submission_id):
    submission = db.session.get(Submission, submission_id)

    rubric = submission.get_rubric()

    # criteria_titles = request.form.getlist('c_title')
    criteria_sequences = request.form.getlist('c_sequence_number')
    scores = request.form.getlist('c_score')
    max_points = request.form.getlist('c_max_points')
    problems = request.form.getlist('c_problemid')
    itemids = request.form.getlist('c_itemid')
    psids = request.form.getlist('c_psid')
    categories = request.form.getlist('c_grading_categories')
    assigned_grade = bool(request.form.get('grades_to_post'))
    rubric_doc = bool(request.form.get('rubric_doc'))

    items = {}
    problemsets = {}

    for itemid_str in itemids:
        try:
            itemid = int(itemid_str)
        except ValueError:
            continue
        if itemid not in items.keys():
            items[itemid] = db.session.query(ProblemSetItem).filter_by(id=itemid).first()
            if items[itemid].problem_id and items[itemid].problem_id not in problemsets.keys():
                problemsets[items[itemid].problem_id] = items[itemid].problem
    for psid_str in psids:
        try:
            psid = int(psid_str)
        except ValueError:
            continue
        if psid not in problemsets.keys():
            problemsets[psid] = db.session.query(ProblemSet).filter_by(id=psid).first()


    for problem_id, criterion_sequence, score, itemid, psid, category, mp in zip(problems, criteria_sequences, scores, itemids, psids, categories, max_points):
        # establish current problemset, problem, and criteria in rubric
        rubric.problem(problemsets[int(psid)]).problem(items[int(itemid)]).criterion(criterion_num=int(criterion_sequence))
        
        # set categories
        for cat in category.split(','):
            try:
                rubric.category(cat)
            except ValueError:
                continue
        
        # apply scores
        try:
            rubric.score(int(score), int(mp))
        except ValueError:
            pass

    submission.set_rubric(rubric.problem().total_scores(True))


    return redirect(url_for('submission_grade', assigned_grade=assigned_grade, post_only=False, submission_id=submission.id, rubric_doc=rubric_doc))


@app.route('/problems')
def problems_page():
    # db.session = Session()

    # Fetch all students and problems
    problems = db.session.query(Problem).all()
    return render_template('problems.j2', 
                           problems=problems)


@app.route('/problem/<int:problem_id>')
def problem_page(problem_id):
    # db.session = Session()
    # Retrieve the problem using the provided foldername
    problem = db.session.query(Problem).filter_by(id=problem_id).first()

    # If the problem doesn't exist, return a 404 error
    if not problem:
        abort(404)

    all_students = db.session.query(Student).all()
    problems = db.session.query(Problem).all()
    courses = db.session.query(Course).all()
    students_by_course = {}
    for course in courses:
        students_by_course[course.id] = [s for s in course.students]
    return render_template('problem.j2', 
                        problems=problems, 
                        courses=courses, 
                        all_students=all_students,
                        students_by_course=students_by_course,
                        problem=problem)


# Teardown context to close and clean up session after each request
@app.teardown_appcontext
def remove_session(*args, **kwargs):
         db.session.remove()


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    
@app.get('/shutdown')
def shutdown():
    shutdown_server()
    return 'Server shutting down...'

@app.before_request
def set_user_email():
    session['user_email'] = 'pbowman@acsamman.edu.jo'

@app.before_request
def load_courses():
    # Query the courses and store them in session
    if not session.get('courses'):
        session['courses'] = [(c.id, c.get_title(), c.termids()) for c in db.session.query(Course).all()]

@app.before_request
def load_terms():
    # db.session = Session()
    # Query the terms and store them in session
    session['terms'] = [(t.id, t.abbreviation) for t in db.session.query(Term).all()]
    session.setdefault('termid', None)

    if not session.get('course_students'):
        update_course_students()

def update_course_students():
    # db.session = Session()
    session['course_students'] = {}
    for course in db.session.query(Course).all():
        session['course_students'][course.id] = [student.id for student in course.students]

# Entry point for the application
if __name__ == '__main__':
        app.run(host="localhost", port=3001, debug=True)
        