from models import *
from gapi_helper import *
from logdef import *


os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
SERVICE = G_Service()

def pull_classrooms(session, email, course_states=['ACTIVE']):
    logger.info(f"pulling classrooms for {email}")
    courses = []
    crcourses = SERVICE.list_courses(course_states)
    for cr in crcourses:
        course = session.query(Course).filter_by(gid=cr['id']).first()
        newcourse = Course(
            gid=cr['id'], 
            title=cr['name'],
            descriptionHeading=cr.get('descriptionHeading'),
            description=cr.get('description'),
            url=cr.get('alternateLink'),
            enrollmentCode=cr.get('enrollmentCode'),
            courseState=cr.get('courseState'),
            section_desc=cr.get('section'),
            creationTime=GAPI_Date.from_cr(cr.get('creationTime')),
            updateTime=GAPI_Date.from_cr(cr.get('updateTime')),
            calendarId=cr.get('calendarId')
            )
        if not course:
            course = newcourse
            session.add(course)
        else:
            newcourse.id = course.id
            course = session.merge(newcourse)
        session.commit()
        session.flush()
        
        if course.descriptionHeading:
            sectionids = course.descriptionHeading.split(",")
            for sectionid in sectionids:
                try:
                    section = session.query(Section).filter_by(ps_dcid=int(sectionid)).first()
                except ValueError:
                    continue
                if section:
                    section.course = course
            session.commit()
            session.flush()

        courses.append(course)

    return courses

def add_student(session, course=None, email=None, gstudent=None, gid=None):
    if gid and not course and not email and not gstudent:
        student = session.query(Student).filter_by(gid=gid).first()
        if not student:
            logger.warning(f"Cannot find student with gid {gid}")
            return None
        return student
    
    gstudent_name = gstudent['profile']['name']['familyName'] + ", " + gstudent['profile']['name']['givenName']
    student = session.query(Student).filter_by(email=email).first()
    if not student:
        student = Student(email=email, gid=gstudent['userId'], name=gstudent_name)
        session.add(student)
    else:
        student = session.merge(Student(id=student.id, email=email, gid=gstudent['userId'], name=gstudent_name))

    session.commit()
    session.flush()
    if student not in course.students:
        course.students.append(student)
    session.commit()
    session.flush()
    return student

def list_students(session, course):
    logger.info(f"adding students for {course.title} to db")
    logger.info("clearing current roster")
    for student in course.students:
        course.students.remove(student)
        session.commit()
        session.flush()
    students = SERVICE.list_students(course)
    for email, gstudent in students.items():
        add_student(session, course, email, gstudent)

def list_coursework(session, course):
    logger.info(f"adding courseworks for {course.title} to db")
    courseworks = []
    gcourseworks = SERVICE.list_coursework(course, [m.name for m in CourseWorkState])
    for gcoursework in gcourseworks:
        coursework = session.query(CourseWork).filter_by(gid=gcoursework['id']).first()
        if not coursework:
            coursework = CourseWork(gid=gcoursework['id'], 
                                    title=gcoursework['title'], 
                                    description=gcoursework.get('description'),
                                    #TODO materials
                                    state=gcoursework['state'],
                                    url=gcoursework.get('alternateLink'),
                                    creationTime=GAPI_Date.from_cr(gcoursework['creationTime']),
                                    updateTime=GAPI_Date.from_cr(gcoursework['updateTime']),
                                    dueDateTime=GAPI_Date.from_cr(gcoursework.get('dueDate'), gcoursework.get('dueTime')),
                                    scheduledTime=GAPI_Date.from_cr(gcoursework.get('scheduledTime')),
                                    maxPoints=gcoursework.get('maxPoints'),
                                    workType=gcoursework.get('workType'),
                                    associatedWithDeveloper=int(gcoursework.get('associatedWithDeveloper', 0)),
                                    assignedToAllStudents=int(gcoursework.get('assigneeMode', 0) == "ALL_STUDENTS"),
                                    creatorUserId=gcoursework.get('creatorUserId'),
                                    topicId=gcoursework.get('topicId'),
                                    )
            session.add(coursework)
        else:
            coursework = CourseWork(
                        id = coursework.id,
                        gid=gcoursework['id'], 
                        title=gcoursework['title'], 
                        description=gcoursework.get('description'),
                        #TODO materials
                        state=gcoursework['state'],
                        url=gcoursework.get('alternateLink'),
                        creationTime=GAPI_Date.from_cr(gcoursework['creationTime']),
                        updateTime=GAPI_Date.from_cr(gcoursework['updateTime']),
                        dueDateTime=GAPI_Date.from_cr(gcoursework.get('dueDate'), gcoursework.get('dueTime')),
                        scheduledTime=GAPI_Date.from_cr(gcoursework.get('scheduledTime')),
                        maxPoints=gcoursework.get('maxPoints'),
                        workType=gcoursework.get('workType'),
                        associatedWithDeveloper=int(gcoursework.get('associatedWithDeveloper', 0)),
                        assignedToAllStudents=int(gcoursework.get('assigneeMode', 0) == "ALL_STUDENTS"),
                        creatorUserId=gcoursework.get('creatorUserId'),
                        topicId=gcoursework.get('topicId'),
                        )
            coursework = session.merge(coursework)
        session.commit()
        session.flush()


        if coursework not in course.courseworks:
            course.courseworks.append(coursework)
        session.commit()
        session.flush()
        for student in coursework.assigned_students:
            coursework.assigned_students.remove(student)
            session.commit()
            session.flush()

        for studentid in gcoursework.get('individualStudentOptions', {}).get('studentIds', []):
            student = add_student(session=session, gid=studentid)
        
            if student not in coursework.assigned_students:
                coursework.students.append(student)
        session.commit()
        session.flush()

def parse_history(submissionHistory):
    history = []
    if not submissionHistory:
        return []
    for event in submissionHistory:
        data = event.get('gradeHistory', event.get('stateHistory'))
        if data: 
            if data.get('state') in ["TURNED_IN", "RETURNED", "CREATED", "RECLAIMED_BY_STUDENT"]:
                history.append(data['state'])
            if data.get('gradeChangeType') == "ASSIGNED_GRADE_POINTS_EARNED_CHANGE":
                history.append(f"ASSIGNED_GRADE {data.get('pointsEarned', '')}".strip())
    return history

def calculate_status(gcsubmission, history=[]):
    submissionHistory = gcsubmission.get('submissionHistory')

    if not history:
        history = parse_history(submissionHistory)
    status = 'ASSIGNED'
    if not history:
        return status

    for event in history:
        if event == "CREATED":
            status = event
        if event.startswith("ASSIGNED_GRADE") or event.startswith("RETURNED"):
            status = "GRADED"
            graded = True
        if event == "TURNED_IN":
            if status == "GRADED":
                status = "RESUBMITTED"
            else:
                status = event
        if event == "RECLAIMED_BY_STUDENT":
            # if they unsubmitted it after resubmitting it, it's still resubmitted
            # because it can only be resubmitted if it's been graded
            if status == "RESUBMITTED": 
                status = "GRADED"
            # if they've reclaimed before grading it, it's still submitted
            # if they've been assigned a grade, it should have been returned also, so status should still be GRADED
    return status

def add_attachment(session, parent, gcattachment):
    url = findkey(gcattachment, ['alternateLink', 'url'])
    if not url:
        logger.warning(f"attachment {gcattachment.get('title', 'unnamed attachment')} has no url")
        return
    attachment = session.query(Attachment).filter_by(url=url).first()
    new_attachment = Attachment(gid=findkey(gcattachment, ['id']),
                                title = gcattachment.get('title', 'attachment'),
                                url = url,
                                thumbnailUrl = findkey(gcattachment, ['thumbnailUrl']),  
                                att_type = list(gcattachment.keys())[0],
                                shareMode = findkey(gcattachment, 'shareMode')
                                )
    if not attachment:
        attachment = new_attachment
        session.add(attachment)
    else:
        new_attachment.id = attachment.id
        attachment = session.merge(new_attachment)
    session.commit()
    session.flush()
    if attachment not in parent.attachments:
        parent.attachments.append(attachment)
    session.commit()
    session.flush()

def list_submissions(session, coursework):
    if coursework.state == CourseWorkState.DRAFT:
        logger.info(f"cannot retrieve submissions for draft coursework {coursework.title}")
        return
    if coursework.state == CourseWorkState.DELETED:
        logger.info(f"cannot retrieve submissions for deleted coursework {coursework.title}")
        return
    logger.info(f"adding submissions for {coursework.title} to db")
    submissions = []

    gsubmissions = SERVICE.list_coursework_submissions(coursework)
    for gsubmission in gsubmissions:
        history = parse_history(gsubmission.get('submissionHistory'))
        submission = session.query(Submission).filter_by(gid=gsubmission['id']).first()
        new_submission = Submission(gid=gsubmission['id'], 
                                state=gsubmission['state'],
                                late=int(gsubmission.get('late', False)),
                                draftGrade=gsubmission.get('draftGrade'),
                                assignedGrade=gsubmission.get('assignedGrade'),
                                creationTime=GAPI_Date.from_cr(gsubmission['creationTime']),
                                updateTime=GAPI_Date.from_cr(gsubmission['updateTime']),
                                url = gsubmission.get('alternateLink'),
                                history = ','.join(history),
                                status = calculate_status(gsubmission, history),
                                )
        if not submission:
            submission = new_submission
            session.add(submission)
        else:
            new_submission.id = submission.id
            submission = session.merge(new_submission)
        session.commit()
        session.flush()

        for attachment in gsubmission.get('assignmentSubmission', {}).get('attachments', []):
            add_attachment(session, submission, attachment)
            session.commit()
            session.flush()

        if submission not in coursework.submissions:
            coursework.submissions.append(submission)
        session.commit()
        session.flush()

        student = session.query(Student).filter_by(gid=gsubmission['userId']).first()
        if student:
            submission.student = student
            session.commit()
            session.flush()


def make_payload(obj, fields=[]):
    payload = {}
    for field in fields:
        if field not in obj.field_categories.WRITABLE_FIELDS.value:
            continue
        if hasattr(obj, field):
            if field in obj.field_categories.ALT_FIELD_NAMES.value:
                payload[obj.field_categories.ALT_FIELD_NAMES.value[field]] = getattr(obj, field)
            else:
                payload[field] = getattr(obj, field)
    return payload

def push_update(session, obj, payload):
    if not obj:
        return
    SERVICE.patch(obj, payload)
    obj = session.merge(obj)
    session.commit()
    session.flush()
    return obj

def pull_gc(session, email):
    courses = pull_classrooms(session, email)
    for course in courses:
        
        list_students(session, course)
        list_coursework(session, course)
        for coursework in course.courseworks:
            list_submissions(session, coursework)
    session.close()

if __name__ == "__main__":
    session = SessionLocal(bind=engine)
    pull_gc(session, "pbowman@acsamman.edu.jo")