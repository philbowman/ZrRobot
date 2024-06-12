from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Table, Enum as SQLEnum
from flask_login import UserMixin
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, sessionmaker
from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import json

from logdef import *
from gapi_helper import *
from autograder import AutoGrader, Rubric
from helpers import *

SQLALCHEMY_DATABASE_URL = "sqlite:///school.db"



class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)
#  = db.Column, db.Integer, db.String, cdb.Float, db.Date, db.DateTime, db.ForeignKey, db.Table, db.Enum

# Association tables for many-to-many relationships
criteria_problem_association = Table('criteria_problem', Base.metadata,
    Column('criteria_id', Integer, ForeignKey('criteria.id')),
    Column('problem_id', Integer, ForeignKey('problems.id'))
)


topic_overall_coursework_association = Table('topic_overall_coursework', Base.metadata,
    Column('topic_overall_cw_id', Integer, ForeignKey('topics.id')),
    Column('overall_for_id', Integer, ForeignKey('courseworks.id'))
)

student_course_association = Table('student_course', Base.metadata,
    Column('student_id', Integer, ForeignKey('students.id')),
    Column('course_id', Integer, ForeignKey('courses.id'))
)

student_section_association = Table('student_section', Base.metadata,
    Column('student_id', Integer, ForeignKey('students.id')),
    Column('section_id', Integer, ForeignKey('sections.id'))
)

coursework_problemset_association = Table('coursework_problemset', Base.metadata,
    Column('coursework_id', Integer, ForeignKey('courseworks.id')),
    Column('problemset_id', Integer, ForeignKey('problemsets.id'))
)

problemset_problem_association = Table('problemset_problem', Base.metadata,
    Column('problemset_id', Integer, ForeignKey('problemsets.id')),
    Column('problem_id', Integer, ForeignKey('problems.id'))
)

section_meeting_association = Table('section_meeting', Base.metadata,
    Column('section_id', Integer, ForeignKey('sections.id')),
    Column('meeting_id', Integer, ForeignKey('meetings.id'))
)

meeting_schoolday_association = Table('meeting_schoolday', Base.metadata,
    Column('meeting_id', Integer, ForeignKey('meetings.id')),
    Column('schoolday_id', Integer, ForeignKey('schooldays.id'))
)

student_coursework_association = Table('student_coursework', Base.metadata,
    Column('student_id', Integer, ForeignKey('students.id')),
    Column('courseworks_id', Integer, ForeignKey('courseworks.id'))
)

coursework_attachment_association = Table('coursework_attachment', Base.metadata,
    Column('coursework_id', Integer, ForeignKey('courseworks.id')),
    Column('attachment_id', Integer, ForeignKey('attachments.id'))
)

submission_attachment_association = Table('submission_attachment', Base.metadata,
    Column('submission_id', Integer, ForeignKey('submissions.id')),
    Column('attachment_id', Integer, ForeignKey('attachments.id'))
)

# Define an actual Enum type for comfort_level
class ComfortLevel(Enum):
    LEAST = "least comfortable"
    LESS = "less comfortable"
    MORE = "more comfortable"
    MOST = "most comfortable"
    ALL = "all comfort levels"

class RequirementType(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CHOICE = "choice"

class CourseWorkState(Enum):
    PUBLISHED = "Published"
    DRAFT = "Draft"
    DELETED = "Deleted"

class SubmissionState(Enum):
    NEW = "New"
    CREATED = "Created"
    TURNED_IN = "Turned in"
    RETURNED = "Returned"
    RECLAIMED_BY_STUDENT = "Reclaimed by student"

class CourseWorkType(Enum):
    ASSIGNMENT = "Assignment"
    SHORT_ANSWER_QUESTION = "Short Answer Question"
    MULTIPLE_CHOICE_QUESTION = "Multiple Choice Question"

class CourseState(Enum):
    ACTIVE = "Active"
    ARCHIVED = "Archived" # The course has been archived. You cannot modify it except to change it to a different state.
    PROVISIONED = "Provisioned" # The course has been created, but not yet activated. It is accessible by the primary teacher and domain administrators, who may modify it or change it to the ACTIVE or DECLINED states. A course may only be changed to PROVISIONED if it is in the DECLINED state.
    DECLINED = "Declined" # The course has been created, but declined. It is accessible by the course owner and domain administrators, though it will not be displayed in the web UI. You cannot modify the course except to change it to the PROVISIONED state. A course may only be changed to DECLINED if it is in the PROVISIONED state.
    SUSPENDED = "Suspended" # The course has been suspended. You cannot modify the course, and only the user identified by the ownerId can view the course. A course may be placed in this state if it potentially violates the Terms of Service.

class CourseFieldCategory(Enum):
    REQUIRED_FIELDS = ['name']
    READONLY_FIELDS = ['id', 'ownerId', 'creationTime', 'updateTime', 'enrollmentCode', 'courseState', 'alternateLink', 'teacherGroupEmail', 'courseGroupEmail', 'teacherFolder', 'courseMaterialSets', 'guardiansEnabled', 'calendarId', 'gradebookSettings']
    WRITABLE_FIELDS = ['name', 'section', 'descriptionHeading', 'description', 'room']
    UPDATE_MASK_FIELDS = ['name', 'section', 'descriptionHeading', 'description', 'room', 'courseState', 'ownerId']
    ALT_FIELD_NAMES  = {'url': 'alternateLink', 'section_desc': 'section'}

class CourseWorkFieldCategory(Enum):
    REQUIRED_FIELDS = ['title']
    READONLY_FIELDS = ['id', 'courseId', 'alternateLink', 'creationTime', 'updateTime', 'associatedWithDeveloper', 'creatorUserId', 'gradeCategory']
    WRITABLE_FIELDS = ['title', 'description', 'materials', 'state', 'dueDate', 'scheduledTime', 'maxPoints', 'workType', 'assigneeMode', 'individualStudentsOptions', 'submissionModificationMode', 'topicId']
    UPDATE_MASK_FIELDS = ['title', 'description', 'state', 'dueDate', 'dueTime', 'maxPoints', 'scheduledTime', 'submissionModificationMode', 'topicId']
    ALT_FIELD_NAMES  = {'url': 'alternateLink', 'section_desc': 'section'}

class MyBase(Base):
    __abstract__ = True
    edited = Column(DateTime)
    pulled = Column(DateTime)

    def get_timestamp(self, kind="edited"):
        ts = None
        try:
            if kind == "edited":
                ts = self.edited
            elif kind == "pulled":
                ts = self.pulled
            elif kind == "created":
                ts = self.creationTime
            elif kind == "updated":
                ts = self.updateTime
            elif kind == "graded":
                if self.rubric:
                    return self.get_rubric()['timestamp']
                return "NA"

        except AttributeError:
            return "NA"
        if ts:
            return ts.strftime("%y-%m-%d %H:%M")
        return None



    def __repr__(self):
        return f"<{self.obj_abbreviation} {self.get_title()}>"

    def get_attributes(self):
        # Filtering out system-defined and other internal attributes
        user_attributes = {key: value for key, value in self.__dict__.items() if not key.startswith('_')}
        attributes_str = ", ".join(f"{key}={value}" for key, value in user_attributes.items())
        return f"{self.__class__.__name__}({attributes_str})"
    
    def get_title(self):
        try:
            return self.title
        except AttributeError:
            try:
                return self.name
            except AttributeError:
                pass
        return 'untitled'

class User(UserMixin):
    def __init__(self, user_id, email):
        self.id = user_id
        self.email = email

class CourseWork(MyBase):
    __tablename__ = 'courseworks'
    gapi_name = 'CourseWork'
    obj_abbreviation = 'CW'

    # db keys
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    topic_id = Column(Integer, ForeignKey('topics.id'))

    # Google API Keys
    # https://developers.google.com/classroom/reference/rest/v1/courses.courseWork
    gid = Column(String)
    title = Column(String)
    description = Column(String)
    # TODO materials
    state = Column(SQLEnum(CourseWorkState))
    url = Column(String) #readonly
    creationTime = Column(DateTime) #readonly, converted
    updateTime = Column(DateTime) #readonly, converted
    dueDateTime = Column(DateTime) #converted from dueDate, dueTime
    scheduledTime = Column(DateTime) #converted
    maxPoints = Column(Integer)
    workType = Column(SQLEnum(CourseWorkType))
    associatedWithDeveloper = Column(Integer) #boolean, readonly
    assignedToAllStudents = Column(Integer) #boolean, if 1:AssigneeMode="ALL_STUDENTS" elif 0:AssigneeMode="INDIVIDUAL_STUDENTS"
    # TODO submissionModificationMode https://developers.google.com/classroom/reference/rest/v1/courses.courseWork#SubmissionModificationMode
    creatorUserId = Column(String) #readonly
    topicId = Column(String)

    # topic_overall = relationship("TopicOverall", backref="coursework")

    #TODO gradeCategory
    # Many-to-many relationship with Attachment
    attachments = relationship("Attachment", secondary=coursework_attachment_association, back_populates="courseworks")

    #TODO union field assignment or multiplechoicequestion

    # Many-to-Many relationship with Student
    assigned_students = relationship("Student", secondary=student_coursework_association, back_populates="courseworks")

    # Many-to-One relationship with Course
    course = relationship("Course", back_populates="courseworks")

    # One-to-Many relationship with Submission
    submissions = relationship("Submission", back_populates="coursework")

    # Many-to-Many relationship with ProblemSet
    problemsets = relationship("ProblemSet", secondary=coursework_problemset_association, back_populates="courseworks")
    
    # Many-to-One relationship with Topic
    topic = relationship("Topic", back_populates="courseworks")

    @classmethod
    def from_topic(cls, topic):
        topic.make_topic_overall()
        if not topic.topic_overall.coursework:
            topic.topic_overall.coursework = cls()
            db.session.commit()
        cw = topic.topic_overall.coursework
        cw.title="OVERALL: " + topic.name
        cw.course=topic.course
        cw.description = "Overall grades for " + topic.name
        cw.topic = topic
        cw.problemsets = [topic.make_problemset()]

        db.session.commit()

        return topic.topic_overall.coursework

    @classmethod
    def from_gradebook(cls, gradebook):
        if not gradebook.coursework:
            gradebook.coursework = cls()
            db.session.commit()
        cw = gradebook.coursework
        cw.title = "OVERALL: " + gradebook.course.get_title()
        cw.course = gradebook.course
        cw.description = "Overall grades for " + gradebook.course.get_title()
        cw.problemsets = [gradebook.make_problemset()]
        db.session.commit()

        return cw

    def ps(self):
        if self.problemsets:
            return self.problemsets[0]
        return None

    def id_string(self):
        return f"cw-{self.id}"

    def filename(self):
        return f"{make_filename(self.title)}---{self.course.gid}-{self.gid}"

    def shortname(self):
        return " ".join(self.title.split("\n")[0].split(" ")[0:3])

    def get_title(self):
        return self.title.replace("\n", " // ")

    def attachment_urls(self):
        return [a.url for a in self.attachments]
    
    def individualStudentsOptions(self):
        if self.assignedToAllStudents:
            return {}
        return {'studentIds': [s.gid for s in self.assigned_students]}
    
    def submission_stats(self):
        stats = {
            "assigned": len(self.assigned_students),
            "ungraded": len([s for s in self.submissions if s.status == "TURNED_IN" or s.status == "RESUBMITTED"]),
            "graded": len([s for s in self.submissions if s.status == "GRADED"]),
            "draftGraded": len([s for s in self.submissions if s.draftGrade is not None]),
            "assignedGraded": len([s for s in self.submissions if s.assignedGrade is not None]),
        }     
        print(stats)
        return stats       

    def frontmatter(self, key:None, value=None):
        kvseparator = "≔ "

        if kvseparator in str(key) or kvseparator in str(value):
            raise Exception("colonequals (≔) cannot be in key or value of frontmatter item")
        if self.description:
            desc = self.description.replace("\r", "")
        else:
            desc = ""
        fmseparator = "---\n"
        kvseparator = "≔"
        if fmseparator in desc:
            start = desc.index(fmseparator)
            end = desc[start + len(fmseparator):].index(fmseparator) + start + len(fmseparator) * 2
            description = desc[:start] + desc[end:]
            frontmatter = desc[start:end]
        else:
            frontmatter = ""
            description = desc
        description = description.strip()
        frontmatter = frontmatter.strip()
        fmlines = frontmatter.split("\n")
        if not key and not value:
            return frontmatter
        
        fmdict = {key: str(value)}
        for line in fmlines:
            if not line or line == "---":
                continue
            elif kvseparator not in line:
                description = line + "\n" + description 
            k = line[:line.index(kvseparator)]
            v = line[line.index(kvseparator) + 1:]
            fmdict.setdefault(k, v)
        
        frontmatter = '\n'.join([f"{k}{kvseparator} {v}" for k, v in fmdict.items()])
        self.description = f"{fmseparator}{frontmatter}\n{fmseparator}\n{description}"
        db.session.commit()

        return frontmatter
        
    def get_topicId(self):
        if self.topic:
            return self.topic.gid
        return None

    def payload(self, keys=[], gcoursework={}, patch=False):
        # Create a new payload for the copied coursework
        payload = {
            "title": self.title,
            "description": self.description,
            "maxPoints": self.maxPoints,
            "workType": 'ASSIGNMENT',
            "topicId": self.get_topicId(),
            }
        
        if self.state:
            if patch and self.state.name == "PUBLISHED":
                payload['state'] = self.state.name

        if self.scheduledTime and self.state.name == "DRAFT":
            payload['scheduledTime'] = GAPI_Date(self.scheduledTime).g_isoformat()

        existing_material_urls = [findkey(material, ['alternateLink', 'url']) for material in gcoursework.get('materials', [])]

        if self.attachments:
            payload['materials'] = [a.payload() for a in self.attachments if a.url not in existing_material_urls]
        if self.dueDateTime:
            if self.dueDateTime > datetime.datetime.now():
                dt = GAPI_Date(self.dueDateTime)
                payload['dueDate'] = dt.dueDate()
                payload['dueTime'] = dt.dueTime() 
            elif not patch:
                dt = GAPI_Date.today()
                payload['dueDate'] = dt.dueDate()
                payload['dueTime'] = dt.dueTime()     

        if patch:
            keys = CourseWorkFieldCategory.UPDATE_MASK_FIELDS.value
            if payload.get('materials'):
                self.frontmatter("materials", ", ".join([a.url for a in self.attachments]))
                payload['description'] = self.description

        if not keys and not gcoursework:
            return payload
        
        p = {}
        for key in payload.keys():
            if keys and key not in keys:
                continue
            elif gcoursework and payload[key] == findkey(gcoursework, key):
                continue
            else:
                p[key] = payload[key]
        return p


class Student(MyBase):
    __tablename__ = 'students'
    gapi_name = 'Student'
    obj_abbreviation = 'STU'
    
    id = Column(Integer, primary_key=True)
    psid = Column(Integer)
    psdcid = Column(Integer)
    gid = Column(String)
    username = Column(String)
    name = Column(String)
    email = Column(String, unique=True)
    grade = Column(Integer)
    
    # Many-to-one relationship with Submission
    submissions = relationship("Submission", back_populates="student")

    # Many-to-Many relationship with Course
    courses = relationship("Course", secondary=student_course_association, back_populates="students")

    # Many-to-Many relationship with Section
    sections = relationship("Section", secondary=student_section_association, back_populates="students")

    # Many-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", secondary=student_coursework_association, back_populates="assigned_students")

    def shortname(self):
        return self.email.split("@")[0]

    def get_submission_for_coursework(self, coursework):
        return db.session.query(Submission).filter_by(coursework_id=coursework.id, student_id=self.id).first()

    def     get_submission_for_problem(self, problem):
        session = db.session
        results = session.query(ProblemSubmission).filter_by(problem_id=problem.id, student_id=self.id).first()
        return results

class Course(MyBase):
    __tablename__ = 'courses'
    field_categories = CourseFieldCategory
    gapi_name = 'Course'
    obj_abbreviation = 'CRS'



    id = Column(Integer, primary_key=True)
    gid = Column(String)
    title = Column(String)
    descriptionHeading = Column(String)
    description = Column(String)
    url = Column(String) #alternateLink on Google API
    enrollmentCode = Column(String)
    courseState = Column(SQLEnum(CourseState))
    section_desc = Column(String) #section on Google API
    creationTime = Column(DateTime) #readonly, converted
    updateTime = Column(DateTime) #readonly, converted
    calendarId = Column(String)

    gradebook_id = Column(Integer, ForeignKey('gradebooks.id'))

    # TODO gradebookSettings https://developers.google.com/classroom/reference/rest/v1/courses#GradebookSettings

    # One-to-One relationship with Gradebook
    gradebook = relationship("Gradebook", back_populates="course")

    # Many-to-Many relationship with Student
    students = relationship("Student", secondary=student_course_association, back_populates="courses")
    
    # One-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", back_populates="course")
    # One-to-Many relationship with Section
    sections = relationship("Section", back_populates="course", foreign_keys="Section.course_id")
    # One-to-Many relationship with Topic
    topics = relationship("Topic", back_populates="course")

    def make_gradebook(self):
        try:
            if not self.gradebook:
                self.gradebook = Gradebook(course=self)
                db.session.commit()
        except Exception as e:
            self.gradebook = Gradebook(course=self)
            db.session.commit()
        self.gradebook.coursework = CourseWork.from_gradebook(self.gradebook)
        self.gradebook.make_problemset()    

        return self.gradebook


    def students_not_in_section(self):
        session = db.session
        cr_emails = [s.email for s in self.students]
        s_emails = []
        for section in self.sections:
            s_emails += [s.email for s in section.students]
        # session.close()

        stu = [e for e in cr_emails if e not in s_emails]
        print(self.title)    
        print(stu)
        return stu
    
    def courseworks_list(self):
        return [cw for cw in self.courseworks if cw.state == "PUBLISHED"]
    
    def get_title(self):
        return self.title + " (" + str(self.section_desc) + ")"
    
    def terms(self):
        return ', '.join(list(set([s.term.get_title() for s in self.sections])))
    
    def termids(self):
        return list(set([s.term.id for s in self.sections]))
    
class Attachment(MyBase):
    __tablename__ = 'attachments'
    writable_id = {'driveFile': 'id', 'youtubeVideo': 'id', 'link': 'url', 'form': 'formUrl'}
    obj_abbreviation = 'ATT'

    id = Column(Integer, primary_key=True)
    gid = Column(String)
    url = Column(String)
    att_type = Column(String, default='link')
    title = Column(String)
    shareMode = Column(String)
    thumbnailUrl = Column(String)

    #Many-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", secondary=coursework_attachment_association, back_populates="attachments")

    #Many-to-Many relationship with Submission
    submissions = relationship("Submission", secondary=submission_attachment_association, back_populates="attachments")

    def student_created(self):
        for u in DISALLOWED_URL_SNIPPETS:
            if u in self.url:
                return False
        return True

    def payload(self):
        if self.writable_id[self.att_type] == 'id':
            payload = {self.att_type: {'id': self.gid}}
        else:
            payload = {'link': {'url': self.url}}

        return payload

    def md_link(self):
        return f"[{self.title}]({self.url})"

    def iframe(self):
        return f'<iframe width="600" height="350" src="{self.url}"></iframe>'

    def parse_attachment(self):
        pass
        # self.writable_data = {self.att_type: {self.writable_id[self.att_type]: findkey(self.gc_material, self.writable_id[self.att_type])}}
        # self.writable_data_link = {'link': {'url': self.url}}
        # if self.shareMode and self.att_type == "driveFile":
        #     self.writable_data_cw = {'driveFile': {'id': self.id, 'shareMode': self.shareMode}}
        # else:
        #     self.writable_data_cw = self.writable_data


class Submission(MyBase):
    __tablename__ = 'submissions'
    gapi_name = 'Submission'
    obj_abbreviation = 'SUB'
    
    id = Column(Integer, primary_key=True)
    gid = Column(String)
    coursework_id = Column(Integer, ForeignKey('courseworks.id'))
    student_id = Column(Integer, ForeignKey('students.id'))
    creationTime = Column(DateTime) #readonly, converted
    updateTime = Column(DateTime) #readonly, converted
    state = Column(SQLEnum(SubmissionState))
    late = Column(Integer) #boolean
    draftGrade = Column(Integer)
    assignedGrade = Column(Integer)
    autograde = Column(Integer)
    url = Column(String) #readonly alternateLink
    history = Column(String) #readonly converted
    status = Column(String) #readonly converted
    rubric = Column(String) # string rep of dict, generated by self.grade()
    rubric_doc_id = Column(String) # id of rubric doc
    # TODO attachments

    # Many-to-Many relationship with Attachment
    attachments = relationship("Attachment", secondary=submission_attachment_association, back_populates="submissions")

    # Many-to-One relationship with Student
    student = relationship("Student", back_populates="submissions")

    # Many-to-One relationship with CourseWork
    coursework = relationship("CourseWork", back_populates="submissions")

    def attachment_urls(self):
        return [a.url for a in self.attachments]

    def filename(self):
        return f"{make_filename(self.student.name)}---{self.gid}"

    def attachment_urls(self):
        return [a.url for a in self.attachments]

    def payload(self):
        return {
            "draftGrade": self.draftGrade,
            "assignedGrade": self.assignedGrade
        }

    def ps(self):
        return self.coursework.ps()

    def rubric_doc(self):
        if not self.rubric_doc_id:
            return None
        docs = [a for a in self.attachments if a.gid == self.rubric_doc_id]
        if not docs:
            return None
        return docs[0]

    def is_overall(self):
        if not self.coursework or not self.coursework.topic or not self.coursework.topic.topic_overall or self.coursework.topic.topic_overall.coursework != self.coursework:
            return False
        return True

    def grade(self, force=False):
        rubric = None
        if not force and not self.is_overall():
            rubric = self.get_rubric()
        try:
            rubric = self.coursework.ps().grade(submission=self, rubric=rubric).total_scores(True)
        except AttributeError as e:
            logger.warning(f"Error grading {self.coursework.title} for {self.student.name}: {e}\n Trying again and ignoring cached rubric.")
            rubric = self.coursework.ps().grade(submission=self, rubric=self.blank_rubric()).total_scores(True)
        self.set_rubric(rubric)
        return rubric
    
    def set_rubric(self, rubric):
        rubric['timestamp'] = str(datetime.datetime.now().strftime("%y-%m-%d %H:%M"))
        self.rubric = json.dumps(rubric, indent=4)
        db.session.commit()

    def assign_draft_grade(self):
        if self.draftGrade and self.draftGrade != self.assignedGrade:
            self.assignedGrade = self.draftGrade
            db.session.commit() 

    def update_score(self, score=None, assigned_grade=False):
        if not score:
            score = self.get_rubric().overall_int()
        if assigned_grade:
            self.assignedGrade = score
            self.draftGrade = None
        elif score != self.assignedGrade or score != self.draftGrade:
            self.draftGrade = score
        if self.draftGrade == self.assignedGrade:
            self.draftGrade = None
        
        db.session.commit()
        return score
    
    def get_title(self):
        return f"{self.student.shortname()}-{self.coursework.shortname()}"

    def blank_rubric(self):
        return Rubric({}, self, self.ps())

    def get_rubric(self, force=False):
        if force:
            return self.grade(force=True)
        if self.rubric:
            try:
                return Rubric(json.loads(self.rubric), self, self.ps())
            except json.JSONDecodeError:
                pass
        return self.blank_rubric()
        
    def html_rubric(self, rubric=None, level=1):
        return self.get_rubric().html()
    
    def markdown_rubric(self):
        return self.get_rubric().md()
    

# class Repository(MyBase):
#     github_username = Column(String)
#     repo_path = Column(String)
#     reponame = Column(String)
#     repolink = Column(String)
#     livelink = Column(String)
#     profilelink = Column(String)
#     repo_exists = Column(Integer)
#     livesite_exists = Column(Integer)
    
#     # many-to-many relationship with submission

#     # many-to-many relationship with student

class ProblemSubmission(MyBase):
    __tablename__ = 'problemsubmissions'
    obj_abbreviation = 'PSUB'
    
    id = Column(Integer, primary_key=True)
    coursework_id = Column(Integer, ForeignKey('courseworks.id'))
    problem_id = Column(Integer, ForeignKey('problems.id')) 
    student_id = Column(Integer, ForeignKey('students.id'))

    github_id = Column(Integer)
    github_url = Column(String)
    github_username = Column(String)
    slug = Column(String)
    email = Column(String)
    
    archive = Column(String)
    checks_passed = Column(Integer)
    checks_run = Column(Integer)
    style50_score = Column(Float)
    timestamp = Column(DateTime)

    manual_grade = Column(Integer)

    student = relationship("Student", backref="problemsubmissions")

    # Many-to-One relationship with Problem
    problem = relationship("Problem", back_populates="problemsubmissions")

class Criterion(MyBase):
    __tablename__ = 'criteria'
    obj_abbreviation = 'CRI'

    id = Column(Integer, primary_key=True)

    sequence = Column(Integer)
    title = Column(String)
    description = Column(String)
    grading_categories = Column(String) #list stored as a string
    max_points = Column(Integer)

    # Many-to-Many relationship with Problem
    problems = relationship("Problem", secondary=criteria_problem_association, back_populates="criteria")

    def criterion_dict(self, item=None, rubric=None):
        d = {
            'title': self.title, 
            'description': self.description,
            'grading_categories': self.get_grading_categories(), 
            'max_points': self.max_points,
            'sequence': self.sequence
            }
        if item and rubric:
            d['score'] = rubric.problem(item).criterion(criterion_title=self.title, criterion_num=self.sequence).score()

        return d


    def get_grading_categories(self):
        return self.grading_categories.upper().split(",")
    
    def set_grading_categories(self, categories:list):
        self.grading_categories = ", ".join(categories)

    def grade(self, submission, rubric):
        return self.target().grade(submission, rubric.problem(self))
    
    def get_title(self):
        return self.target().get_title()
    
    def id_string(self):
        return self.target().id_string()

class Problem(MyBase):
    __tablename__ = 'problems'
    obj_abbreviation = 'PROB'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    foldername = Column(String)
    slug = Column(String)
    autograder = Column(String)
    url = Column(String)
    allow_delete = Column(Integer)
    manual_criteria = Column(Integer) #boolean
    avg_method = Column(String, default='bool')

    problemset_items = relationship('ProblemSetItem', back_populates='problem')

    # One-to-Many relationship with ProblemSubmission
    problemsubmissions = relationship("ProblemSubmission", back_populates="problem")

    # Many-to-Many relationship with Criterion
    criteria = relationship("Criterion", secondary=criteria_problem_association, back_populates="problems")
    
    def criteria_dict(self, item=None, psid=None, rubric=None):
        manual_criteria = {}
        for criterion in self.criteria:
            manual_criteria[criterion.title] = criterion.criterion_dict(item, rubric)
        return {self.id_string(): {'itemid': item.id, 'psid': psid, 'criteria': manual_criteria, 'title': self.title, 'url': self.url}}
    
    def criteria_by_sequence(self):
        # return a list of items sorted by sequence
        sequenced_criteria = sorted([c for c in self.criteria if c.sequence], key=lambda criterion: criterion.sequence)
        
        if len(sequenced_criteria) == len(self.criteria):
            return sequenced_criteria
        
        # add sequence numbers to criteria that don't have them
        cur = 0
        all_sequenced_criteria = sequenced_criteria + [s for s in self.criteria if not c.sequence]
        for c in all_sequenced_criteria:
            c.sequence = cur
            cur += 1
        db.session.commit()

        return all_sequenced_criteria
    
    def grade(self, rubric):
        if not self.avg_method:
            self.avg_method = "bool"
            db.session.commit()
        autograder = AutoGrader(self)
        return autograder.grade(rubric)
    
    def __str__(self):
        if self.title:
            return self.title
        if self.slug:
            return slug_to_foldername(self.slug)
        return self.autograder
    
    def get_title(self):
        return str(self)

    def id_string(self):
        return f"prob-{self.id}"

class ProblemSet(MyBase):
    __tablename__ = 'problemsets'
    obj_abbreviation = 'PS'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    num_required = Column(Integer, default=0)

    # topic_overall = relationship("TopicOverall", backref="problemset")

    # Many-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", secondary=coursework_problemset_association, back_populates="problemsets")
    
    # One-to-Many relationship with ProblemSetItem
    items = relationship("ProblemSetItem", back_populates="problemset", foreign_keys="ProblemSetItem.problemset_id")

    def nested_courseworks(self):
        return [item.target() for item in self.nested_items if item.target().__class__.__name__ == "CourseWork"]

    # def topic_overall(self, student, rubric=None):
    #     if not rubric:
    #         rubric = Rubric({}, None, self)
    #     for coursework in self.nested_courseworks():
    #         rubric.problem(coursework)
    #     return rubric

    def grade(self, submission=None, rubric=None, student=None):
        if not rubric:
            if submission and not student:
                student = submission.student
            rubric = Rubric({}, submission, self, student)

        for item in self.items:
            item.grade(submission, rubric, student)

        return rubric
    
    def get_title(self):
        return self.title

    def problemsets(self):
        return [item.target() for item in self.items_by_sequence() if item.target().__class__.__name__ == "ProblemSet"]

    def problems(self):
        return [item.target() for item in self.items_by_sequence() if item.target().__class__.__name__ == "Problem"]

    def problems_recursive(self):
        problems = self.problems()
        for problemset in self.problemsets():
            problems += problemset.problems_recursive()
        return problems

    def manual_input_problems(self, rubric=None):
        mip = [item.problem.criteria_dict(item=item, psid=self.id, rubric=rubric) for item in self.items_by_sequence() if item.problem and item.problem.criteria]
        for problemset in self.problemsets():
            mip += problemset.manual_input_problems(rubric)
        return mip
    
    def items_by_sequence(self):
        # return a list of items sorted by sequence
        for item in self.items:
            if not item.sequence:
                item.sequence = 0
        return sorted(self.items, key=lambda item: item.sequence)

    def items_by_requirement(self, requirement_type):
        if type(requirement_type) is str:
            req  = RequirementType[requirement_type]
        else:
            req = requirement_type
        return [i for i in self.items_by_sequence() if i.requirement_type == req]

    def adjust_num_required(self):
        req_choice_count = len(self.items_by_requirement('REQUIRED') + self.items_by_requirement('CHOICE'))
        if self.num_required < req_choice_count:
            self.num_required = req_choice_count

    def adjust_item_sequence(self):
        # adjust sequence numbers so they are sequential and unique
        items = self.items_by_sequence()
        for i, item in enumerate(items):
            item.sequence = i + 1
        return items
    
    def id_string(self):
        return f"ps-{self.id}"


class ProblemSetItem(MyBase):
    __tablename__ = 'problemset_items'
    obj_abbreviation = 'PS_I'

    id = Column(Integer, primary_key=True)
    problemset_id = Column(Integer, ForeignKey('problemsets.id'))
    problem_id = Column(Integer, ForeignKey('problems.id'), nullable=True)
    nested_problemset_id = Column(Integer, ForeignKey('problemsets.id'), nullable=True)
    nested_coursework_id = Column(Integer, ForeignKey('courseworks.id'), nullable=True)
    comfort_level = Column(SQLEnum(ComfortLevel))

    sequence = Column(Integer)
    requirement_type = Column(SQLEnum(RequirementType))

    nested_coursework = relationship('CourseWork', backref='nested_items', foreign_keys=[nested_coursework_id])

    problem = relationship('Problem', back_populates='problemset_items')
    nested_problemset = relationship('ProblemSet', backref='nested_items', foreign_keys=[nested_problemset_id])
    problemset = relationship('ProblemSet', back_populates='items', foreign_keys=[problemset_id])

    @classmethod
    def from_coursework(cls, problemset, coursework, comfort=None, requirement=None):
        item = db.session.query(ProblemSetItem).filter_by(nested_coursework_id=coursework.id).first()
        if not item:
            item =  ProblemSetItem(problemset=problemset, nested_coursework=coursework, requirement_type=RequirementType.REQUIRED)
            db.session.add(item)
        if item.problemset_id != problemset.id:
            item.problemset_id = problemset.id
        if comfort:
            item.comfort_level = ComfortLevel[comfort]
        item.comfort_level =  item.comfort_level or ComfortLevel.LEAST
        if requirement:
            item.requirement_type = RequirementType[requirement]
        item.requirement_type = item.requirement_type or RequirementType.REQUIRED
        db.session.commit()
        return item

    def grade(self, submission, rubric, student=None):
        if submission and not student:
            student = submission.student
        if self.problem:
            return self.problem.grade(rubric.problem(self))
        if self.nested_problemset:
            return self.nested_problemset.grade(submission, rubric.problem(self), student)
        if self.nested_coursework:
            sub = student.get_submission_for_coursework(self.nested_coursework)
            return rubric.problem(self).coursework(sub.get_rubric())

    def get_title(self):
        return self.target().get_title()
    
    def id_string(self):
        return self.target().id_string()
    
    def target(self):
        if self.nested_coursework:
            return self.nested_coursework
        if self.problem:
            return self.problem
        elif self.nested_problemset:
            return self.nested_problemset
        return None

class School(MyBase):
    __tablename__ = 'schools'
    abbrevaition = 'SCH'

    id = Column(Integer, primary_key=True)
    ps_id = Column(Integer)
    abbreviation = Column(String)

    sections = relationship('Section', back_populates='school', foreign_keys="Section.school_id")

class Section(MyBase):
    __tablename__ = 'sections'
    obj_abbreviation = 'SEC'

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey('schools.id')) 
    course_id = Column(Integer, ForeignKey('courses.id')) 
    term_id = Column(Integer, ForeignKey('terms.id'))

    teacher = Column(String)
    course_name = Column(String)
    period_number = Column(Integer)
    no_of_students = Column(Integer)
    room = Column(String)
    teacher_email = Column(String)
    ps_dcid = Column(Integer, unique=True)
    period_abbreviation = Column(String)
    term_abbreviation = Column(String)

    # Many-to-Many relationship with Student
    students = relationship("Student", secondary=student_section_association, back_populates="sections")
    
    # Many-to-One relationship with Term
    term = relationship("Term", back_populates="sections")
    school = relationship('School', back_populates='sections', foreign_keys=[school_id])
    meetings = relationship('Meeting', secondary=section_meeting_association, back_populates='sections')

    # Many-to-One relationship with Course
    course = relationship("Course", back_populates="sections")

    def get_title(self):
        return f"{self.period_abbreviation}-{self.course_name} ({self.teacher}) {self.term_abbreviation}"

class Year(MyBase):
    __tablename__ = 'years'
    obj_abbreviation = 'YR'

    id = Column(Integer, primary_key=True)
    ps_dcid = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    abbreviation = Column(String)

    terms = relationship('Term', back_populates='year', foreign_keys="Term.year_id")

class Term(MyBase):
    __tablename__ = 'terms'
    obj_abbreviation = 'TRM'

    id = Column(Integer, primary_key=True)
    year_id = Column(Integer, ForeignKey('years.id'))
    ps_dcid = Column(String)
    abbreviation = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)

    year = relationship("Year", back_populates="terms")
    sections = relationship('Section', back_populates='term', foreign_keys="Section.term_id")

    def get_title(self):
        if self.year:
            return f"{self.abbreviation} {self.year.abbreviation}"
        if self.start_date and self.end_date:
            return f"{self.abbreviation} {str(self.start_date.year)[-2:]}-{str(self.end_date.year)[-2:]}"
        return self.abbreviation

class SchoolDay(MyBase):
    __tablename__ = 'schooldays'
    obj_abbreviation = 'SCHDY'

    id = Column(Integer, primary_key=True)
    date_value = Column(Date)
    date = Column(Date)

    meetings = relationship('Meeting', secondary=meeting_schoolday_association, back_populates='schooldays')

class Meeting(MyBase):
    __tablename__ = 'meetings'
    obj_abbreviation = 'MTG'

    id = Column(Integer, primary_key=True)
    bell_schedule = Column(String)
    start_time = Column(Integer)
    end_time = Column(Integer)
    term_name = Column(String)
    cycle_day_letter = Column(String)
    period_abbreviation = Column(String)
    period_number = Column(Integer)

    schooldays = relationship('SchoolDay', secondary=meeting_schoolday_association, back_populates='meetings')
    sections = relationship('Section', secondary=section_meeting_association, back_populates='meetings')

class TopicOverall(MyBase):
    __tablename__ = 'topic_overalls'
    obj_abbreviation = 'TPC_OVR'

    id = Column(Integer, primary_key=True)
    problemset_id = Column(Integer, ForeignKey('problemsets.id'))
    coursework_id = Column(Integer, ForeignKey('courseworks.id'))

    problemset = relationship('ProblemSet', backref='topic_overall', uselist=False)
    coursework = relationship('CourseWork', backref='topic_overall', uselist=False)
    topic = relationship('Topic', back_populates='topic_overall')

    def course(self):
        return self.topic[0].course

class Gradebook(MyBase):
    __tablename__ = 'gradebooks'
    obj_abbreviation = 'GBK'

    id = Column(Integer, primary_key=True)
    # course_id = Column(Integer, ForeignKey('courses.id'))

    # One-to-One relationship with Course
    # course = relationship("Course", back_populates="gradebook")
    problemset = relationship('ProblemSet', backref='topic_overall', uselist=False)
    coursework = relationship('CourseWork', backref='topic_overall', uselist=False)

    def make_problemset(self):
        overall_ps = self.problemset
        if overall_ps:
            overall_ps.title = "OVERALL: " + self.course.get_title()
            db.session.commit()
        else:
            overall_ps = ProblemSet(title="OVERALL: " + self.course.get_title())
            self.problemset = overall_ps
        
        overall_ps.items = []
        for topic in self.course.topics:
            if topic.topic_overall and topic.topic_overall.coursework:
                overall_ps.items.append(ProblemSetItem.from_coursework(overall_ps, topic.topic_overall.coursework))
        
        db.session.commit()
        return overall_ps


class Topic(MyBase):
    __tablename__ = 'topics'
    obj_abbreviation = 'TPC'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    gid = Column(String)
    course_id = Column(Integer, ForeignKey('courses.id'))
    topic_overall_id = Column(Integer, ForeignKey('topic_overalls.id'))

    # Many-to-One relationship with Course
    course = relationship("Course", back_populates="topics")

    topic_overall = relationship('TopicOverall', back_populates='topic')

    courseworks = relationship('CourseWork', back_populates='topic')

    def make_topic_overall(self):
        if not self.topic_overall:
            self.topic_overall = TopicOverall()
            db.session.commit()
        return self.topic_overall

    def make_problemset(self):
        self.make_topic_overall()
        overall_ps = self.topic_overall.problemset
        if overall_ps:
            overall_ps.title = "OVERALL: " + self.name
            db.session.commit()
        else:
            overall_ps = ProblemSet(title="OVERALL: " + self.name)
            self.topic_overall.problemset = overall_ps
        overall_ps.items = [ProblemSetItem.from_coursework(overall_ps, cw) for cw in self.courseworks if cw != self.topic_overall.coursework and cw.problemsets]
        db.session.commit()
        return overall_ps

    def grade_all(self, student):
        oa_cw = CourseWork.from_topic(self)
        for cw in self.courseworks:
            student.get_submission_for_coursework(cw).grade()
        self.grade(student, makeps=False)


    def grade(self, student, makeps=True):
        if makeps:
            self.make_problemset()
        overall_cw = self.topic_overall.coursework
        if overall_cw:
            for ps in overall_cw.problemsets:
                overall_cw.problemsets.remove(ps)
                db.session.commit()
                db.session.flush()  
            overall_cw.problemsets.append(self.overall_ps)
            db.session.commit()
            submission = student.get_submission_for_coursework(overall_cw)
            return submission.grade()
        else:
            return self.overall_ps.grade(None, student=student)




# Creating SQLite database
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )

# Create tables
# Base.metadata.create_all(engine)

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
