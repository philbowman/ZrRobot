from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Table, Enum as SQLEnum
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

class MyBase(Base):
    __abstract__ = True

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"

    def get_attributes(self):
        # Filtering out system-defined and other internal attributes
        user_attributes = {key: value for key, value in self.__dict__.items() if not key.startswith('_')}
        attributes_str = ", ".join(f"{key}={value}" for key, value in user_attributes.items())
        return f"{self.__class__.__name__}({attributes_str})"

class CourseWork(MyBase):
    __tablename__ = 'courseworks'
    gapi_name = 'CourseWork'
    
    # db keys
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'))

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
    topicId = Column(String) # TODO associate with Topic object

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

    def individualStudentsOptions(self):
        if self.assignedToAllStudents:
            return {}
        return {'studentIds': [s.gid for s in self.assigned_students]}
    
    def submission_stats(self):
        stats = {
            "assigned": len(self.assigned_students),
            "ungraded": len([s for s in self.submissions if s.status == "TURNED_IN" or s.status == "RESUBMITTED"]),
            "graded": len([s for s in self.submissions if s.status == "GRADED"]),
        }     
        print(stats)
        return stats       


class Student(MyBase):
    __tablename__ = 'students'
    
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


    def get_submission_for_problem(self, problem):
        session = db.session
        results = session.query(ProblemSubmission).filter_by(problem_id=problem.id, student_id=self.id).first()
        return results

class Course(MyBase):
    __tablename__ = 'courses'
    field_categories = CourseFieldCategory
    gapi_name = 'Course'

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

    # TODO gradebookSettings https://developers.google.com/classroom/reference/rest/v1/courses#GradebookSettings

    # Many-to-Many relationship with Student
    students = relationship("Student", secondary=student_course_association, back_populates="courses")
    
    # One-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", back_populates="course")
    # One-to-Many relationship with Section
    sections = relationship("Section", back_populates="course", foreign_keys="Section.course_id")

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
class Attachment(MyBase):
    __tablename__ = 'attachments'
    writable_id = {'driveFile': 'id', 'youtubeVideo': 'id', 'link': 'url', 'form': 'formUrl'}
    
    id = Column(Integer, primary_key=True)
    gid = Column(String)
    url = Column(String)
    att_type = Column(String)
    title = Column(String)
    shareMode = Column(String)
    thumbnailUrl = Column(String)

    #Many-to-Many relationship with CourseWork
    courseworks = relationship("CourseWork", secondary=coursework_attachment_association, back_populates="attachments")

    #Many-to-Many relationship with Submission
    submissions = relationship("Submission", secondary=submission_attachment_association, back_populates="attachments")

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
    # TODO attachments

    # Many-to-Many relationship with Attachment
    attachments = relationship("Attachment", secondary=submission_attachment_association, back_populates="submissions")

    # Many-to-One relationship with Student
    student = relationship("Student", back_populates="submissions")

    # Many-to-One relationship with CourseWork
    coursework = relationship("CourseWork", back_populates="submissions")

    def grade(self):
        rubric = self.coursework.problemsets[0].grade(submission=self).total_scores()
        rubric['timestamp'] = str(datetime.datetime.now())
        self.rubric = json.dumps(rubric, indent=4)
        return rubric
    
    def get_rubric(self, force=False):
        if self.rubric and not force:
            try:
                return json.loads(self.rubric)
            except json.JSONDecodeError:
                return self.grade()
        else:
            return self.grade()
        
    def html_rubric(self, rubric=None, level=1):
        return self.grade().html()

class ProblemSubmission(MyBase):
    __tablename__ = 'problemsubmissions'
    
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


class Problem(MyBase):
    __tablename__ = 'problems'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    foldername = Column(String)
    slug = Column(String)
    autograder = Column(String)
    url = Column(String)
    allow_delete = Column(Integer)

    problemset_items = relationship('ProblemSetItem', back_populates='problem')

    # One-to-Many relationship with ProblemSubmission
    problemsubmissions = relationship("ProblemSubmission", back_populates="problem")

    def grade(self, submission, rubric):
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
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    num_required = Column(Integer, default=0)

    # Many-to-Many relationship with CourseWork (remains unchanged)
    courseworks = relationship("CourseWork", secondary=coursework_problemset_association, back_populates="problemsets")
    
    # One-to-Many relationship with ProblemSetItem
    items = relationship("ProblemSetItem", back_populates="problemset", foreign_keys="ProblemSetItem.problemset_id")

    def grade(self, submission, rubric=None):
        # session = db.session
        if not rubric:
            rubric = Rubric({}, submission, self)

        for item in self.items:
            item.grade(submission, rubric)

        return rubric
    
    def get_title(self):
        return self.title

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

    id = Column(Integer, primary_key=True)
    problemset_id = Column(Integer, ForeignKey('problemsets.id'))
    problem_id = Column(Integer, ForeignKey('problems.id'), nullable=True)
    nested_problemset_id = Column(Integer, ForeignKey('problemsets.id'), nullable=True)
    comfort_level = Column(SQLEnum(ComfortLevel))

    sequence = Column(Integer)
    requirement_type = Column(SQLEnum(RequirementType))

    problem = relationship('Problem', back_populates='problemset_items')
    nested_problemset = relationship('ProblemSet', backref='nested_items', foreign_keys=[nested_problemset_id])
    problemset = relationship('ProblemSet', back_populates='items', foreign_keys=[problemset_id])

    def grade(self, submission, rubric):
        return self.target().grade(submission, rubric.problem(self))
    
    def get_title(self):
        return self.target().get_title()
    
    def id_string(self):
        return self.target().id_string()
    
    def target(self):
        if self.problem:
            return self.problem
        elif self.nested_problemset:
            return self.nested_problemset
        return None
        

class School(MyBase):
    __tablename__ = 'schools'

    id = Column(Integer, primary_key=True)
    ps_id = Column(Integer)
    abbreviation = Column(String)

    sections = relationship('Section', back_populates='school', foreign_keys="Section.school_id")

class Section(MyBase):
    __tablename__ = 'sections'

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

    def title(self):
        return f"{self.period_abbreviation}-{self.course_name} ({self.teacher}) {self.term_abbreviation}"

class Year(MyBase):
    __tablename__ = 'years'

    id = Column(Integer, primary_key=True)
    ps_dcid = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    abbreviation = Column(String)

    terms = relationship('Term', back_populates='year', foreign_keys="Term.year_id")

class Term(MyBase):
    __tablename__ = 'terms'

    id = Column(Integer, primary_key=True)
    year_id = Column(Integer, ForeignKey('years.id'))
    ps_dcid = Column(String)
    abbreviation = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)

    year = relationship("Year", back_populates="terms")
    sections = relationship('Section', back_populates='term', foreign_keys="Section.term_id")

class SchoolDay(MyBase):
    __tablename__ = 'schooldays'

    id = Column(Integer, primary_key=True)
    date_value = Column(Date)
    date = Column(Date)

    meetings = relationship('Meeting', secondary=meeting_schoolday_association, back_populates='schooldays')

class Meeting(MyBase):
    __tablename__ = 'meetings'

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
    

# Creating SQLite database
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )

# Create tables
# Base.metadata.create_all(engine)

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
