from models import *
from gapi_helper import *
from logdef import *


os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
SERVICE = G_Service()

def make_rubric_doc(session, submission):
    title = f"RUBRIC for {submission.coursework.title} - {submission.student.name}"
    doc = SERVICE.update_google_doc(submission.markdown_rubric(), title, submission.rubric_doc_id)

    payload = {"addAttachments": {"driveFile": {"id": doc["documentId"]}}}
    if doc["documentId"] != submission.rubric_doc_id:
        updated_gsubmission = SERVICE.add_submission_attachments(submission.coursework.course.gid, submission.coursework.gid, submission.gid, payload)

        add_submission(session, submission.coursework, updated_gsubmission)
        submission.rubric_doc_id = doc["documentId"]
        session.commit()
        session.flush()
    return submission.rubric_doc()


def create_coursework(session, coursework):
    new_gcoursework = SERVICE.create_coursework(coursework.course.gid, coursework.payload())
    new_coursework = add_coursework(session, coursework.course, new_gcoursework, coursework)
    return new_coursework

def pull_classrooms(session, email, course_states=['ACTIVE']):
    logger.info(f"pulling classrooms for {email}")
    crcourses = SERVICE.list_courses(course_states)
    courses = []
    for gcourse in crcourses:
        course = add_course(session, gcourse)
        courses.append(course)
    return courses

def add_course(session, gcourse=None, course=None):
    if course and not gcourse:
        gcourse = SERVICE.get_course(course.gid)
    if gcourse and not course:
        course = session.query(Course).filter_by(gid=gcourse['id']).first()
    newcourse = Course(
        gid=gcourse['id'], 
        title=gcourse['name'],
        descriptionHeading=gcourse.get('descriptionHeading'),
        description=gcourse.get('description'),
        url=gcourse.get('alternateLink'),
        enrollmentCode=gcourse.get('enrollmentCode'),
        courseState=gcourse.get('courseState'),
        section_desc=gcourse.get('section'),
        creationTime=GAPI_Date.from_cr(gcourse.get('creationTime')),
        updateTime=GAPI_Date.from_cr(gcourse.get('updateTime')),
        calendarId=gcourse.get('calendarId')
        )
    if not course:
        course = newcourse
        session.add(course)
    else:
        newcourse.id = course.id
        course = session.merge(newcourse)
    course.pulled = datetime.datetime.now()
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
        course.pulled = datetime.datetime.now()
        session.commit()
        session.flush()
    
    list_topics(session, course)

    return course

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

    student.pulled = datetime.datetime.now()
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

def copy_coursework(session, coursework, w_submissions=True, draft=True):
    gcoursework = SERVICE.get_coursework(coursework.course.gid, coursework.gid)
    logger.info(f"copying coursework {coursework.title}") 
    new_gcoursework = SERVICE.copy_coursework(coursework.course.gid, gcoursework, draft=draft)
    new_coursework = add_coursework(session, coursework.course, new_gcoursework)
    

    if w_submissions and new_gcoursework['state'] == 'PUBLISHED':
        list_submissions(session, new_coursework)
        copy_submissions(session, coursework, new_coursework)
    return new_coursework

def copy_submissions(session, source_cw, target_cw):
    for submission in source_cw.submissions:
        new_submission = patch_submission(session, source_submission=submission, target_cw=target_cw)
        payload = {"addAttachments": []}
        for attachment in submission.attachments:
            if attachment.url not in new_submission.attachment_urls():
                payload['addAttachments'].append(attachment.payload())
        if payload['addAttachments']:
            new_gsubmission = SERVICE.add_submission_attachments(target_cw.course.gid, target_cw.gid, new_submission.gid, payload)
            add_submission(session, target_cw, new_gsubmission)

def patch_coursework(session, coursework, payload=None):
    if not payload:
        payload = coursework.payload(patch=True)
    if not payload:
        return coursework
    new_gcoursework = SERVICE.patch_coursework(coursework_gid=coursework.gid, course_gid=coursework.course.gid, payload=payload)
    coursework.edited = datetime.datetime.now()
    return add_coursework(session, coursework.course, new_gcoursework, coursework)

def patch_submission(session, target_cw, source_submission=None, payload=None):
    gsubmission = None
    if source_submission and not payload:
        payload = source_submission.payload()
    if source_submission and target_cw == source_submission.coursework:
        target_submission = source_submission
    else:
        target_submission = session.query(Submission).filter_by(coursework=target_cw, student=source_submission.student).first()
    if 'assignedGrade' in payload:  
        gsubmission = SERVICE.get_submission(target_submission.coursework.course.gid, target_submission.coursework.gid, target_submission.gid)
        for k in list(payload.keys()):
            if payload.get(k) == gsubmission.get(k):
                del payload[k]
    if payload:
        logger.info(f"patching submission {target_submission.get_title()} with {payload}")
        gsubmission = SERVICE.patch_submission(target_submission.gid, target_cw.gid, target_cw.course.gid, payload)
        target_submission.edited = datetime.datetime.now()
    if gsubmission:
        return add_submission(session, target_cw, gsubmission, submission=target_submission)
    return target_submission

def list_coursework(session, course):
    logger.info(f"adding courseworks for {course.title} to db")
    courseworks = []
    gcourseworks = SERVICE.list_coursework(course, [m.name for m in CourseWorkState])
    courseworks = []
    for gcoursework in gcourseworks:
        courseworks.append(add_coursework(session, course, gcoursework))
    return courseworks

def list_topics(session, course):
    logger.info(f"adding topics for {course.title} to db")
    topics = []
    gtopics = SERVICE.list_topics(course.gid)
    for gtopic in gtopics:
        topic = add_topic(session, course, gtopic)
        topics.append(topic)
    return topics


def add_topic(session, course, gtopic):
    topic = session.query(Topic).filter_by(gid=gtopic['topicId']).first()
    if not topic:
        topic = Topic(gid=gtopic['topicId'], name=gtopic['name'])
        session.add(topic)
    else:
        topic = session.merge(Topic(id=topic.id, gid=gtopic['topicId'], name=gtopic['name']))
    topic.pulled = datetime.datetime.now()
    session.commit()
    session.flush()
    if topic not in course.topics:
        course.topics.append(topic)
    session.commit()
    session.flush()
    return topic

def get_gtopic(session, course=None, course_id=None, topic=None, topic_id=None):
    if topic and not topic_id:
        topic_id = topic.gid
    if course and not course_id:
        course_id = course.gid
    return SERVICE.get_topic(course_id, topic_id)

def get_gsubmission(session, submission):
    return SERVICE.get_submission(submission.coursework.course.gid, submission.coursework.gid, submission.gid)

def get_gcoursework(session, coursework):
    return SERVICE.get_coursework(coursework.course.gid, coursework.gid)

def add_coursework(session, course=None, gcoursework=None, coursework=None):
    if gcoursework and not coursework:
        coursework = session.query(CourseWork).filter_by(gid=gcoursework['id']).first()
    if coursework and not course:
        course = coursework.course
    if coursework and not gcoursework:
        gcoursework = get_gcoursework(session, coursework)
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
    coursework.pulled = datetime.datetime.now()
    session.commit()
    session.flush()


    for attachment in gcoursework.get('materials', []):
        add_attachment(session, coursework, attachment)
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

    if coursework.topicId:
        topic = session.query(Topic).filter_by(gid=coursework.topicId).first()
        if not topic:
            topic = add_topic(session, course, get_gtopic(session, course, topic_id=coursework.topicId))
        if topic:
            coursework.topic = topic

    return coursework

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
                                title = findkey(gcattachment, 'title'),
                                url = url,
                                thumbnailUrl = findkey(gcattachment, ['thumbnailUrl']),  
                                att_type = list(gcattachment.keys())[0],
                                shareMode = findkey(gcattachment, 'shareMode')
                                )
    if new_attachment.att_type == "driveFile":
        new_attachment.gid = findkey(gcattachment, ['id'])
    if new_attachment.att_type == "link":
        if "docs.google.com" in new_attachment.url and "document" in new_attachment.url:
            new_attachment.gid = new_attachment.url.split("/")[new_attachment.url.index("document") + 2]
    if not attachment:
        attachment = new_attachment
        session.add(attachment)
    else:
        new_attachment.id = attachment.id
        attachment = session.merge(new_attachment)
    attachment.pulled = datetime.datetime.now()
    session.commit()
    session.flush()
    if attachment not in parent.attachments:
        parent.attachments.append(attachment)
    session.commit()
    session.flush()
    return attachment

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
        submission = add_submission(session, coursework, gsubmission)

def add_submission(session, coursework=None, gsubmission=None, submission=None):
    if submission and not gsubmission:
        gsubmission = get_gsubmission(session, submission)
    if submission and not coursework:
        coursework = submission.coursework
    history = parse_history(gsubmission.get('submissionHistory'))
    if not submission:
        submission = session.query(Submission).filter_by(gid=gsubmission['id']).first()
    new_submission = Submission(gid=gsubmission['id'], 
                            state=gsubmission['state'],
                            late=int(gsubmission.get('late', False)),
                            draftGrade=gsubmission.get('draftGrade'),
                            assignedGrade=gsubmission.get('assignedGrade'),
                            creationTime=gsubmission['creationTime'],
                            updateTime=gsubmission['updateTime'],
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
    submission.pulled = datetime.datetime.now()
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
    return submission


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
    doc = SERVICE.update_google_doc("hi\nthere\n", "TEST", "11RkHytzKjB7w3huKLsnVZlLdsQXW7J_FTXnzyyA9OKU")
    print(doc)