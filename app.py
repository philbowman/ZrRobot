from flask import Flask, render_template, request, abort, flash, redirect, url_for, g, session

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
app.secret_key = 'banana'
# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URL
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.debug = True
db.init_app(app)
migrate = Migrate(app, db)
with app.app_context():
    db.create_all()

# Initialize a scoped session to ensure that each HTTP request has its own session 
# which is based on the greenlet's current identifier.
# Session = scoped_session(SessionLocal, scopefunc=greenlet.getcurrent)

# Define constants
STUDENTWORK_DIR = "studentwork"
COMPARE50_DIR = "compare50"  # This appears unused for now. If you intend to use it, ensure you do, or else remove it.
COURSE_ID = 1872
TOKEN = '25e0c040383247d6a9e3d2ca9c54d4e6'  # Note: Avoid hardcoding sensitive data in the script. Consider environment variables or config files.

comfort_levels = [member.name.lower() for member in ComfortLevel]

requirement_types = [member.name.lower() for member in RequirementType]

@app.route('/section/<int:section_id>/pull_roster')
def update_section_roster(section_id):
    # db.session = Session()
    section = db.session.query(Section).filter_by(id=section_id).first()
    make_ps_roster(db.session, section)
    flash('Updated section roster!', 'success')
    return redirect(request.referrer)



@app.route('/set_term', methods=['POST'])
def set_term():
    selected_term = request.form.get('term')
    print(selected_term)
    # Set session['term'] to the selected term
    try:
        session['termid'] = int(selected_term)
    except ValueError:
        session['termid'] = None
    # Redirect back to the referring page (the page where the form was submitted)
    return redirect(request.referrer)

def refresh_data(kind):
    # db.session = Session()
    if kind == 'all':
        kinds = ['gc', 'ps', 'cs50']
    else:
        kinds = [kind]
    if 'ps' in kinds:
        schools = {hs_schoolid: "HS"}
        section_events, bell_schedules, day_schedules = list_section_events(db.session, schools)
        for section in db.session.query(Section).filter_by(teacher_email=session['user_email']).all():
            make_ps_roster(db.session, section)
        flash('Refreshed PowerSchool Data!', 'success')
    if 'gc' in kinds:
        pull_gc(db.session, session['user_email'])
        update_course_students()
        flash('Refreshed Google Classroom Data!', 'success')
    if 'cs50' in kinds:
        cs50data = Submit50(COURSE_ID, TOKEN, STUDENTWORK_DIR)
        cs50data.pull_projects(compare=True)
        cs50data.write_to_db(db.session)
        flash('Refreshed CS50 Data!', 'success')
    

@app.route('/refresh/all')
def refresh_all():
    refresh_data('all')
    return redirect(url_for('main_page'))

@app.route('/refresh/gc')
def refresh_gc():
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

@app.route('/course/<int:course_id>', methods=['GET', 'POST'])
def course_page(course_id):
    # db.session = Session()
    # Fetch course
    course = db.session.query(Course).filter_by(id=course_id).first()
    sections = db.session.query(Section).filter_by(course_id=course_id).all()
    # Fetch all students in the section
    # students = db.session.query(Student).filter_by(section_id=section_id).all()

    if request.method == 'POST':
        pass
    return render_template('course.j2', course=course, sections=sections)

@app.route('/courses')
def courses_page():
    # db.session = Session()
    # Fetch all courses
    courses = db.session.query(Course).all()
    return render_template('courses.j2', courses=courses)

# Main route to display all students and problems
@app.route('/')
def main_page():


    return render_template('main.j2')

@app.route('/section/<int:section_id>', methods=['GET', 'POST'])
def section_page(section_id):
    # db.session = Session()
    # Fetch section
    section = db.session.query(Section).filter_by(id=section_id).first()
    courses = db.session.query(Course).all()
    # Fetch all students in the section
    # students = db.session.query(Student).filter_by(section_id=section_id).all()

    if request.method == 'POST':
        print(request.form)
        if not request.form['course']:
            section.course = None
        
        course = db.session.query(Course).filter_by(id=request.form['course']).first()
        section.course = course
        db.session.commit()
        course.descriptionHeading = ','.join([str(s.ps_dcid) for s in course.sections])
        course.section_desc = ';'.join([s.title() for s in course.sections])
        payload = make_payload(course, ['descriptionHeading', 'section_desc'])
        push_update(db.session, course, payload)
        flash('Updated section!', 'success')
        return redirect(url_for('sections_page'))


    return render_template('section.j2', section=section, courses=courses)



@app.route('/problem/create', methods=['GET', 'POST'])
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
        problem.allow_delete = 1

        if not problem_id:
            db.session.add(problem)

        db.session.commit()
        flash(f"{'Updated' if problem_id else 'Created'} problem successfully!", 'success')
        return redirect(url_for('problems_page'))

    return render_template(
        'edit_problem.j2',
        problem=problem,
        comfort_levels=comfort_levels,
        # Add other data as needed for editing problems
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
        app.db.session.delete(problemset)
        app.db.session.commit()
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
        
    if request.method == 'POST':
        title = request.form['title']
        selected_problems = request.form.getlist('problems')  # Get selected problem IDs as a list
        number_required = request.form['number_required']
        comforts = request.form.getlist('comfort_levels')
        requirements = request.form.getlist('requirement_types')
        sequences = request.form.getlist('sequence')

        problemset = ProblemSet()

        problemset.title = title
        problemset.num_required = int(number_required)

        problemset.items.clear()
        db.session.commit()

        # Associate selected problems with the problemset
        for problem_id, comfort, req_type, sequence in zip(selected_problems, comforts, requirements, sequences):
            # Ensure problem_id is an integer
            if problem_id.startswith('prob-'):
                problem_id = int(problem_id[5:])
                item = ProblemSetItem(problem_id=problem_id, comfort_level=comfort, requirement_type=req_type, sequence=int(sequence))
                

            elif problem_id.startswith('ps-'):
                problem_id = int(problem_id[3:])
                item = ProblemSetItem(nested_problemset_id=problem_id, comfort_level=comfort, requirement_type=req_type, sequence=int(sequence))
            db.session.add(item)
            problemset.items.append(item)

        problemset.adjust_num_required()

        db.session.commit()

        ps_items = problemset.adjust_item_sequence()
        db.session.commit()

        flash(f"{'Updated' if problemset_id else 'Created'} problemset successfully!", 'success')
        return redirect(request.referrer)

    problems = db.session.query(Problem).all()
    problem_sets = db.session.query(ProblemSet).all()

    return render_template(
        'edit_problemset.j2',
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
    return render_template('problemsets.j2', problemsets=problemsets)



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

@app.route('/coursework/<int:coursework_id>')
def coursework_page(coursework_id):
    # db.session = Session()
    # Get the coursework from the database
    coursework = db.session.get(CourseWork, coursework_id)
    problemsets = db.session.query(ProblemSet).all()

    # Return a 404 error if the coursework is not found
    if not coursework:
        abort(404)


    return render_template('coursework.j2', coursework=coursework, problemsets=problemsets)

@app.route('/submission/<int:submission_id>')
def submission_page( submission_id):
    submission = db.session.get(Submission, submission_id)
    return render_template('submission.j2', submission=submission, grade=None)


@app.route('/submission/<int:submission_id>/grade')
def submission_grade(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission.coursework.problemsets:
        flash('No problemsets associated with this coursework!', 'error')
        return redirect(request.referrer)
    rubric = submission.grade()

    return render_template('submission.j2', submission=submission)

@app.route('/problems')
def problems_page():
    # db.session = Session()

    # Fetch all students and problems
    all_students = db.session.query(Student).all()
    problems = db.session.query(Problem).all()
    courses = db.session.query(Course).all()
    students_by_course = {}
    for course in courses:
        students_by_course[course.id] = [s for s in course.students]
    return render_template('problems.j2', 
                           problems=problems, 
                           courses=courses, 
                           all_students=all_students,
                           students_by_course=students_by_course)


@app.route('/problem/<foldername>')
def problem_page(foldername):
    # db.session = Session()
    # Retrieve the problem using the provided foldername
    problem = db.session.query(Problem).filter_by(foldername=foldername).first()

    # If the problem doesn't exist, return a 404 error
    if not problem:
        abort(404)

    # Get all submissions associated with the problem
    submissions = db.session.query(ProblemSubmission).filter_by(problem_id=problem.id).all()



    return render_template('problem.j2', problem=problem, submissions=submissions)

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
def load_terms():
    # db.session = Session()
    # Query the terms and store them in g.terms
    session['terms'] = [(t.id, t.abbreviation) for t in db.session.query(Term).all()]
    session.setdefault('termid', None)
    if not session.get('course_students'):
        update_course_students()

def update_course_students():
    # db.session = Session()
    session['course_students'] = {}
    for course in db.session.query(Course).all():
        session['course_students'][course.id] = [student.id for student in course.students]

@app.route('/coursework/<int:coursework_id>/requirements', methods=['POST'])
def update_requirements(coursework_id):
    # db.session = Session()
    coursework = db.session.get(CourseWork, coursework_id)
    requirements = request.form.getlist('requirements')
    if not coursework:
        flash('Coursework not found!', 'error')
        return redirect(request.referrer)
    for req in coursework.problemsets:
        coursework.problemsets.remove(req)
        db.session.commit()
        db.session.flush()
    for req in requirements:
        try:
            ps = db.session.get(ProblemSet, int(req))
            coursework.problemsets.append(ps)
            db.session.commit()
            db.session.flush()
        except ValueError:
            flash(f'Problemset {req} not found!', 'error')

    db.session.commit()
    flash('Updated requirements!', 'success')
    return redirect(request.referrer)


# Entry point for the application
if __name__ == '__main__':
    app.run()
