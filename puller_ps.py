from logdef import *
from ps_query import *
from runtimer import *
from secrets_parameters import *
from models import *
from sqlalchemy import create_engine
import greenlet


def add_schools(session, schools):
    for school in schools:
        s = session.query(School).filter_by(ps_id=school, abbreviation=schools[school]).first()
        if not s:
            s = School(ps_id=school, abbreviation=schools[school])
            session.add(s)
        else:
            s = session.merge(School(id=s.id, ps_id=school, abbreviation=schools[school]))
        session.commit()
        session.flush()

def add_section(session, section):
    logger.info("adding section " + section['period_abbreviation'] + "-" + section['course_name'])
    teacher = section['lastfirst']
    course = section['course_name']
    period_number = int(section['period_number'])
    no_of_students = int(section['no_of_students'])
    term_abbreviation = section['term_name']
    # room = section['room']
    if 'teacher_email' in section.keys():
        teacher_email = section['teacher_email']
    else:
        teacher_email = ""
    ps_dcid = int(section['section_dcid'])
    period_abbreviation = section['period_abbreviation']
    
    dbsection = session.query(Section).filter_by(ps_dcid=ps_dcid).first()
    if not dbsection:
        dbsection = Section(term_abbreviation=term_abbreviation, teacher=teacher, course_name=course, period_number=period_number, no_of_students=no_of_students, teacher_email=teacher_email, ps_dcid=ps_dcid, period_abbreviation=period_abbreviation)
        session.add(dbsection)
    else:
        dbsection = session.merge(Section(id=dbsection.id, term_abbreviation=term_abbreviation, teacher=teacher, course_name=course, period_number=period_number, no_of_students=no_of_students, teacher_email=teacher_email, ps_dcid=ps_dcid, period_abbreviation=period_abbreviation))
    
    session.commit()
    session.flush()

    school = session.query(School).filter_by(ps_id=section['schoolid']).first()
    school.sections.append(dbsection)
    session.commit()
    session.flush()
    for dcid in section['term_dcids']:

        term = session.query(Term).filter_by(ps_dcid=dcid).first()
        term.sections.append(dbsection)
        session.commit()
        session.flush()

    return dbsection



def add_meeting(session, meeting):
    logger.info("adding meeting")
    bell_schedule = meeting['bell_schedule']
    start_time = int(meeting['start_time'])
    end_time = int(meeting['end_time'])
    term_name = meeting['term_name']
    cycle_day_letter = meeting['cycle_day_letter']
    period_abbreviation = meeting['period_abbreviation']
    period_number = int(meeting['period_number'])

    dbmeeting = session.query(Meeting).filter_by(start_time=start_time, end_time=end_time).first()
    if not dbmeeting:
        dbmeeting = Meeting(start_time=start_time, end_time=end_time, bell_schedule=bell_schedule, term_name=term_name, cycle_day_letter=cycle_day_letter, period_abbreviation=period_abbreviation, period_number=period_number)
        session.add(dbmeeting)
    else:
        dbmeeting = session.merge(Meeting(id=dbmeeting.id, start_time=start_time, end_time=end_time, bell_schedule=bell_schedule, term_name=term_name, cycle_day_letter=cycle_day_letter, period_abbreviation=period_abbreviation, period_number=period_number))
    session.commit()
    session.flush()

    return dbmeeting

@runtimer
def list_section_events(session, schools, pull=False):

    try:
        # List section events
        section_events, terms = PSQuery.list_section_events(schools=schools, pull=pull)
    except Exception as e:
        logger.error("Failed to list section events.")
        logger.error(e)
        if pull:
            return
        logger.info("Retrying with pull=True")
        section_events, terms = PSQuery.list_section_events(schools=schools, pull=True)
        
    
    for dcid, t in terms.items():
        # Create Term
        term = session.query(Term).filter_by(ps_dcid=dcid).first()
        if not term:
            term = Term(ps_dcid=dcid, year_id=t['yearid'], abbreviation=t['abbreviation'], start_date=datetime.datetime.strptime(t['start_date'], "%Y-%m-%d").date(), end_date=datetime.datetime.strptime(t['end_date'], "%Y-%m-%d").date())
            session.add(term)
        else:
            term = session.merge(Term(id=term.id, year_id=t['yearid'], ps_dcid=dcid, abbreviation=t['abbreviation'], start_date=datetime.datetime.strptime(t['start_date'], "%Y-%m-%d").date(), end_date=datetime.datetime.strptime(t['end_date'], "%Y-%m-%d").date()))
        session.commit()
        session.flush()

        # Create year
        year = session.query(Year).filter_by(ps_dcid=t['yearid']).first()
        if not year:
            year = Year(ps_dcid=t['yearid'], start_date=datetime.datetime.strptime(t['year_firstday'], "%Y-%m-%d").date(), end_date=datetime.datetime.strptime(t['year_lastday'], "%Y-%m-%d").date(), abbreviation=t['year_abbreviation'])
            session.add(year)
        else:
            year = session.merge(Year(id=year.id, ps_dcid=t['yearid'], start_date=datetime.datetime.strptime(t['year_firstday'], "%Y-%m-%d").date(), end_date=datetime.datetime.strptime(t['year_lastday'], "%Y-%m-%d").date(), abbreviation=t['year_abbreviation']))

    # List bell schedules
    try:
        bell_schedules, day_schedules = PSQuery.list_bell_schedules(schools=schools, pull=pull)
    except Exception as e:
        logger.error("Failed to list bell schedules.")
        logger.error(e)
        if pull:
            return
        logger.info("Retrying with pull=True")
        bell_schedules, day_schedules = PSQuery.list_bell_schedules(schools=schools, pull=True)
        
    
    # Add schools to db
    add_schools(session, schools)

    for section_dcid, section in section_events.items():
        # Add section to db
        dbsection = add_section(session, section)


        # for meeting in section['meetings']:
        #     # Create datetime object from date string
        #     day = datetime.datetime.strptime(meeting['date'], "%Y-%m-%d")

        #     # Add school day to db
        #     dbday = session.query(SchoolDay).filter_by(date=day).first()
        #     if not dbday:
        #         dbday = SchoolDay(date=day)
        #         session.add(dbday)
        #         session.commit()

        #     # Add meeting to db    
        #     dbmeeting = add_meeting(session, meeting)

        #     dbmeeting.schooldays.append(dbday)
        #     dbmeeting.sections.append(dbsection)

        #     session.commit()

    session.close()
    return (section_events, bell_schedules, day_schedules)

def make_ps_roster(session, section):
    psstudents =  Query().roster({'section_dcid': section.ps_dcid})
    # for student in [s for s in section.students]:
    #     section.students.remove(student)
    #     session.commit()
    #     session.flush()
    desired_students = []
    for student in psstudents:
        # students_dcid
        # students_id
        # last_name
        # first_name
        # lastfirst
        # grade_level
        # email
        # sections_dcid
        # sections_id    
        dbstudent = session.query(Student).filter_by(email=student['email']).first()
        if not dbstudent:
            dbstudent = Student(
                email=student['email'], 
                psid=student['students_id'], 
                psdcid=student['students_dcid'],
                name=student['lastfirst'],
                grade=student['grade_level']
                )
            session.add(dbstudent)            
        else:
            dbstudent = session.merge(Student(
                id=dbstudent.id,
                email=student['email'].lower(), 
                psid=student['students_id'], 
                psdcid=student['students_dcid'],
                name=student['lastfirst'],
                grade=student['grade_level']
                ))
        # section.students.append(dbstudent)
        session.commit()
        session.flush()
        desired_students.append(dbstudent)
    section.students.clear()
    section.students = desired_students
    session.commit()
    return section.students


if __name__ == "__main__":
    schools = {hs_schoolid: "HS"}
    list_section_events(schools, pull=True)