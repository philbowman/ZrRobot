from __future__ import print_function
import os.path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
# from google_auth_oauthlib.flow import Flow

from dateutil import parser

from secrets_parameters import *
from helpers import *
from logdef import *
from my_retry import *
from models import *


class G_Service:
    cw_writable_keys = ["title", "description", "maxPoints", "topicId", "gradeCategory", "assigneeMode", "individualStudentOptions", "dueDate", "dueTime", "scheduledTime", "state"]
    def __init__(self) -> None:
        self.calendar = self.make_service("calendar")
        self.classroom = self.make_service("classroom")
        self.drive = self.make_service("drive")
        self.docs = self.make_service("docs")

    def create_google_doc(self, title):
        # Create a new Google Doc
        document = self.docs.documents().create(body={'title': title or "NEW DOCUMENT"}).execute()
        return document

    def update_google_doc(self, content, title=None, doc_id=None, replace_all=True):
        document = None
        if not doc_id:
            # Create a new Google Doc
            document = self.create_google_doc(title)
            doc_id = document['documentId']
        else:
            document = self.docs.documents().get(documentId=doc_id).execute()

        if replace_all:            
            last_char_index = max([c['endIndex'] for c in document['body']['content']])-1
            if last_char_index > 1:
                requests = [
                    {
                        'deleteContentRange': {
                            'range': {
                                'startIndex': 1,
                                'endIndex': last_char_index,
                            }

                        }

                    },
                ]
                document = self.docs.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1,
                    },
                    'text': content,
                }
            }
        ]


        self.docs.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

        return document

    @my_retry
    def copy_coursework(self, course_id, coursework, new_title=None, new_due_datetime=None, draft=True):
        if not new_title:
            new_title = "_" + coursework.get("title", "")
        
        # Create a new payload for the copied coursework
        new_coursework_payload = {
            "title": new_title,
            "description": coursework.get("description", ""),  # You can copy the description if needed
            "maxPoints": coursework.get("maxPoints", 100),  # You can set a default value or copy the maxPoints
            "state": coursework.get("state", "DRAFT"),  # You can set a default value or copy the state
            "workType": 'ASSIGNMENT'
        }
        if draft:
            new_coursework_payload['state'] = "DRAFT"
        if not new_due_datetime:
            if coursework.get("dueDate"):
                new_due_datetime = GAPI_Date.from_cr(coursework.get("dueDate"), coursework.get("dueTime"))
                if new_due_datetime < GAPI_Date.today():
                    new_due_datetime = GAPI_Date.today()
        if new_due_datetime:
            new_coursework_payload['dueDate'] = new_due_datetime.dueDate()
            new_coursework_payload['dueTime'] = new_due_datetime.dueTime()
        

        # Create the copied coursework
        copied_coursework = self.create_coursework(course_id, new_coursework_payload)

        return copied_coursework

    @my_retry
    def copy_submission_grades(self, submission, coursework, course, draftGrade, assignedGrade):
        # Create a new payload for the copied submission
        new_submission_payload = {
            "draftGrade": draftGrade,  # You can copy the draftGrade if needed
            "assignedGrade": assignedGrade,  # You can copy the assignedGrade if needed
            "state": submission.get("state", "NEW"),  # You can set a default value or copy the state
        }
        # Create the copied submission
        copied_submission = self.create_submission(coursework, submission.student, new_submission_payload)
        return copied_submission




    @my_retry
    def add_submission_attachments(self, course_id, coursework_id, submission_id, attachment_payload):
        logger.info(f"ADDING ATTACHMENTS to {submission_id} - {attachment_payload}")
        result = self.classroom.courses().courseWork().studentSubmissions().modifyAttachments(courseId=course_id, courseWorkId=coursework_id, id=submission_id, body=attachment_payload).execute()
        return self.parse_submission(result)

    @my_retry
    def return_submission(self, submission):
        logger.info(f"RETURNING {submission}")
        response = self.classroom.courses().courseWork().studentSubmissions().return_(courseId=submission.coursework.classroom.id, courseWorkId=submission.coursework.id, id=submission.id)

    @my_retry
    def list_topics(self, course_id):
        response = self.classroom.courses().topics().list(courseId=course_id).execute()
        return response.get('topic', [])

    @my_retry
    def get_topic(self, course_id, topic_id):
        response = self.classroom.courses().topics().get(courseId=course_id, id=topic_id).execute()
        return response

    @my_retry
    def create_coursework(self, course_id, payload):
        logger.info(f"Creating coursework in {course_id}: {payload}")
        cw =  self.classroom.courses().courseWork().create(courseId=course_id, body=payload).execute()
        return self.parse_cw(cw)

    @my_retry
    def list_coursework(self, course, coursework_states=["PUBLISHED"]):
        response = self.classroom.courses().courseWork().list(courseWorkStates = coursework_states, courseId=course.gid).execute()
        result = response.get('courseWork', []) 
        token = response.get('nextPageToken', None)
        while token:
            response = self.classroom.courses().courseWork().list(pageToken=token, courseWorkStates = coursework_states, courseId=course.gid).execute()
            result += response.get('courseWork', [])
            token = response.get('nextPageToken', None)        
        return [self.parse_cw(cw) for cw in result]

    def parse_cw(self, cw):
        cw['cidid'] = f"{cw['courseId']}-{cw['id']}"
        cw['dueDateTime'] = GAPI_Date.from_cr(cw.get('dueDate'), cw.get('dueTime'))
        for k in ['creationTime', 'updateTime', 'scheduledTime']:
            cw[k] = GAPI_Date.from_cr(cw.get(k))
        return cw

    @my_retry
    def list_student_submissions(self, student, course, submission_states=None):
        if submission_states:
            results = self.classroom.courses().courseWork().studentSubmissions().list(userId=student.email, states=submission_states, courseWorkId="-", courseId=course.id, pageSize=1000).execute()
        else:
            results = self.classroom.courses().courseWork().studentSubmissions().list(userId=student.email,courseWorkId="-", courseId=course.id, pageSize=1000).execute()
        submissions = results.get('studentSubmissions', [])            
        return [self.parse_submission(s) for s in submissions]

    def parse_submission(self, s):
        s['cidid'] = f"{s['courseWorkId']}-{s['id']}"
        for k in ['creationTime', 'updateTime']:
            s[k] = GAPI_Date.from_cr(s.get(k))
        return s

    @my_retry
    def list_coursework_submissions(self, coursework, submission_states=None):
        if submission_states:
            response = self.classroom.courses().courseWork().studentSubmissions().list(states=submission_states, courseWorkId=coursework.gid, courseId=coursework.course.gid).execute()
            result = response.get('studentSubmissions', []) 
            token = response.get('nextPageToken', None)
            while token:
                response = self.classroom.courses().courseWork().studentSubmissions().list(nextPageToken=token, states=submission_states, courseWorkId=coursework.gid, courseId=coursework.course.gid).execute()
                result += response.get('courseWork', [])
                token = response.get('nextPageToken', None)    
        else:
            response = self.classroom.courses().courseWork().studentSubmissions().list(courseWorkId=coursework.gid, courseId=coursework.course.gid).execute()
            result = response.get('studentSubmissions', []) 
            token = response.get('nextPageToken', None)
            while token:
                response = self.classroom.courses().courseWork().studentSubmissions().list(nextPageToken=token, courseWorkId=coursework.gid, courseId=coursework.course.gid).execute()
                result += response.get('studentSubmissions', [])
                token = response.get('nextPageToken', None)  
    
        if not result:
            return []

        return [self.parse_submission(s) for s in result]

    @my_retry
    def get_submission(self, course_gid, coursework_gid, submission_gid):
        submission = self.parse_submission(self.classroom.courses().courseWork().studentSubmissions().get(id=submission_gid, courseWorkId=coursework_gid, courseId=course_gid).execute())
        return self.parse_submission(submission)


    @my_retry
    def get_coursework(self, course_gid, coursework_gid):
        cw = self.classroom.courses().courseWork().get(id=coursework_gid, courseId=course_gid).execute()
        return self.parse_cw(cw)
    
    @my_retry
    def get_course(self, course_gid):
        course = self.classroom.courses().get(id=course_gid).execute()
        return course
    
    @my_retry
    def get_student(self, student_gid):
        student = self.classroom.userProfiles().get(userId=student_gid).execute()
        return student
    
    @my_retry
    def patch_submission(self, submission_gid, coursework_gid, course_gid, payload):
        updatemask = ','.join([k for k in payload.keys()])
        # Create the copied submission
        patched_submission =  self.classroom.courses().courseWork().studentSubmissions().patch(id=submission_gid, courseWorkId=coursework_gid, courseId=course_gid, body=payload, updateMask=updatemask).execute()
        return self.parse_submission(patched_submission)
    

    def patch_coursework(self, coursework_gid, course_gid, payload):
        updatemask = ','.join([k for k in payload.keys()])
        cw = self.classroom.courses().courseWork().patch(id=coursework_gid, courseId=course_gid, body=payload, updateMask=updatemask).execute()
        return self.parse_cw(cw)

    @my_retry
    def patch(self, obj, payload):
        updatemask = ','.join([k for k in payload.keys() if k in obj.field_categories.UPDATE_MASK_FIELDS.value])
        if not updatemask:
            return None
        try:
            if obj.gapi_name == "Course":
                return self.classroom.courses().patch(id=obj.gid, body=payload, updateMask=updatemask).execute()
            if not obj.associatedWithDeveloper:
                return None
            if obj.gapi_name == "CourseWork":
                cw = self.classroom.courses().courseWork().patch(id=obj.gid, courseId=obj.classroom.gid, body=payload, updateMask=updatemask).execute()
                return self.parse_cw(cw)
            if obj.gapi_name == "Submission":
                submission =  self.classroom.courses().courseWork().studentSubmissions().patch(id=obj.gid, courseWorkId=obj.coursework.gid, courseId=obj.coursework.course.gid, body=payload, updateMask=updatemask).execute()
                return self.parse_submission(submission)
        except AttributeError as e:
            logger.warning(e)
        return None
    # @my_retry
    # def get_user_profile(self, userid):
        
    @my_retry
    def list_students(self, classroom):
        response = self.classroom.courses().students().list(courseId=classroom.gid, pageSize=300).execute()
        result = response.get('students', [])
        token = response.get('nextPageToken', None)
        while token:
            response = self.classroom.courses().students().list(courseId=classroom.gid, pageSize=300, pageToken=token).execute()
            result += response.get('students', [])
            token = response.get('nextPageToken', None)
        student_emails = [student['profile']['emailAddress'] for student in result]
        students = {student['profile']['emailAddress'].lower(): student for student in result}
        return students

    # @my_retry
    # def update_course(self, course, payload):
    #     try:
    #         courseid = int(course)
    #     except:
    #         courseid = course.id
    #     updatemask = ','.join([k for k in payload.keys()])
    #     return self.classroom.courses().patch(id=courseid, body=payload, updateMask=updatemask).execute()

    @my_retry
    def list_courses(self, course_states=["ACTIVE"]):
        # Call the Classroom API
        response = self.classroom.courses().list(courseStates=course_states, pageSize=500).execute()
        results = response.get('courses', [])
        token = response.get('nextPageToken', None)
        while token:
            response = self.classroom.courses().list(courseStates=course_states, pageSize=500, pageToken=token).execute()
            results += response.get('courses', [])
            token = response.get('nextPageToken', None)
        for c in results:
            c['name-id'] = f"{c['name']}---{c['id']}"
        
        if not results:
            logger.info('No courses found.')
            return []
        return results

    def add_student(self, classroomid, enrollmentcode, userid):
        return self.classroom.courses().students().create(courseId=classroomid, enrollmentCode = enrollmentcode, body={'userId': userid}).execute()

    @my_retry
    def list_events(self, calendarid, timemin, timemax, extendedproperty=None, maxresults=500, q=None):
        if extendedproperty:
            events = self.calendar.events().list(singleEvents="true", timeMin=timemin, timeMax=timemax, sharedExtendedProperty=extendedproperty, maxResults=maxresults, calendarId=calendarid).execute().get('items', [])    
        elif q:
            events = self.calendar.events().list(singleEvents="true", timeMin=timemin, timeMax=timemax, q=q, maxResults=maxresults, calendarId=calendarid).execute().get('items', [])    
        else:
            events = self.calendar.events().list(maxResults=maxresults, calendarId=calendarid, timeMin=timemin, timeMax=timemax).execute().get('items', [])
        return events 
        
    @my_retry
    def make_service(self, type=None):
        SCOPES = ["https://www.googleapis.com/auth/drive", 
        'https://www.googleapis.com/auth/classroom.courses.readonly', 
        'https://www.googleapis.com/auth/classroom.courses',
        'https://www.googleapis.com/auth/classroom.coursework.students', 
        'https://www.googleapis.com/auth/classroom.rosters', 
        'https://www.googleapis.com/auth/classroom.profile.emails', 
        'https://www.googleapis.com/auth/classroom.rosters.readonly', 
        'https://www.googleapis.com/auth/classroom.topics.readonly',
        'https://www.googleapis.com/auth/calendar', 
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/classroom.coursework.me',
        'https://www.googleapis.com/auth/classroom.student-submissions.me.readonly',
        'https://www.googleapis.com/auth/classroom.student-submissions.students.readonly',
        'https://www.googleapis.com/auth/documents'
        ]
        
        creds = None
        
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        if type == "calendar":
            return build('calendar', 'v3', credentials=creds) 
        if type == "classroom":
            return build('classroom', 'v1', credentials=creds)
        elif type == "drive":
            return build('drive', 'v3', credentials=creds)
        elif type == 'docs':
            return build('docs', 'v1', credentials=creds)
        else:
            return {"classroom_service": build('classroom', 'v1', credentials=creds), "drive_serice": build('drive', 'v3', credentials=creds)}


# ChatGPT
def is_g_isoformat(s):
    iso_formats = {
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,6}Z$': '%Y-%m-%dT%H:%M:%S.%fZ',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}Z$': '%Y-%m-%dT%H:%M:%S.%fZ',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,6}(Z|\+\d{2}:\d{2})$': '%Y-%m-%dT%H:%M:%S.%f%z',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{1,9}(Z|\+\d{2}:\d{2})$': '%Y-%m-%dT%H:%M:%S.%f%z',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$': '%Y-%m-%dT%H:%M:%SZ',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$': '%Y-%m-%dT%H:%MZ',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|\+\d{2}:\d{2})$': '%Y-%m-%dT%H:%M:%S%z',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$': '%Y-%m-%dT%H:%M:%S',
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$': '%Y-%m-%dT%H:%M',
    r'^\d{4}-\d{2}-\d{2}$': '%Y-%m-%d',
    }
    for pattern, format_string in iso_formats.items():
        if re.compile(pattern).match(s):
            return format_string
    return None

class GAPI_Date(datetime.datetime):
    tzoffset = TIMEZONE_OFFSET
    @classmethod
    def from_cr(cls, cr_date, cr_time=None, offset=None):
            if not offset:
                offset = cls.tzoffset
            if not cr_date:
                return None
            if type(cr_date) is cls:
                return cr_date
            if type(cr_date) is str:
                try:
                    if cr_date[-5] == ".":
                        return cls(datetime.datetime.strptime(cr_date, '%Y-%m-%dT%H:%M:%S.%fZ') + datetime.timedelta(hours=offset))
                    return cls(datetime.datetime.strptime(cr_date.removesuffix('Z'), '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=offset))
                except ValueError:
                    parsed_dt = parser.parse(cr_date)
                    result = cls(parsed_dt + datetime.timedelta(hours=offset))
                    logger.warn(f"Used sloppy parser for {cr_date}: {result}")
                    return result
            if type(cr_date) is dict:
                y = cr_date['year']
                m = cr_date['month']
                d = cr_date['day']
                if not y or not m or not d:
                    return None
                if cr_time:
                    hr = cr_time.get('hours', 23)
                    mi = cr_time.get('minutes', 59)
                else:
                    hr = 23
                    mi = 59
                return cls(datetime.datetime(y, m, d, hr, mi) + datetime.timedelta(hours=offset))
            if type(cr_date) is datetime.datetime:
                return cls(cr_date + datetime.timedelta(hours=offset))

            return None
    
    @classmethod
    def today(cls):
        now = datetime.datetime.now()
        return cls(datetime.datetime(now.year, now.month, now.day, 23, 59))

    def __new__(cls, *args, **kwargs):
        if args[0] is None:
            return None
        if isinstance(args[0], datetime.datetime):
            dt = args[0]
            return datetime.datetime.__new__(cls, dt.year, dt.month, dt.day, dt.hour, dt.minute)
        if isinstance(args[0], datetime.date):
            dt = args[0]
            return datetime.datetime.__new__(cls, dt.year, dt.month, dt.day, 23, 59)
        
        if type(args[0]) is str:
            date_format = is_g_isoformat(args[0])
            if date_format:
                return cls(datetime.datetime.strptime(args[0], date_format))
        return datetime.datetime.__new__(cls, *args, **kwargs)
    
    def __str__(self):
        return self.isoformat()
    def no_offset(self):
        return self - datetime.timedelta(hours=self.__class__.tzoffset)
    def g_isoformat(self):
        return self.no_offset().isoformat() + "Z"
    def dueDate(self):
        converted = self.no_offset()
        return {'day': converted.day, 'month': converted.month, 'year': converted.year}
    def dueTime(self):
        converted = self.no_offset()
        return {'hours': converted.hour, 'minutes': converted.minute}

