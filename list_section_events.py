from logdef import *
from ps_query import *
from runtimer import *
from secrets_parameters import *
from models import *

import datetime, pytz, time, csv, pandas, json


from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, func
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()


def garbage(schoolid, date=None):
    # Create the database engine and tables
    engine = create_engine('sqlite:///school.db')
    Base.metadata.create_all(engine)

    # Create a session to interact with the database
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create PS client
    client = Query()

    if not date:
        date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Create a School instance
    school = School(ps_id=schoolid, abbreviation="HS")
    session.add(school)
    session.commit()


    # Query terms
    psterms = client.terms(date, school.ps_id)
    session.query(ProblemSet).filter_by()
    start_dates = []
    end_dates = []
    schedules = {school.ps_id: {}}
    for t in psterms:
        start_dates.append(t['firstday'])
        end_dates.append(t['lastday'])
        term = session.query(ProblemSet).filter_by(ps_dcid=t['dcid']).first()
        if not term:
            term = Term(ps_id=t['dcid'], name=t['name'], abbreviation=t['abbreviation'], firstday=t['firstday'], lastday=t['lastday'], school=school))
        else:
             term = session.merge(Term(id=term.id, ps_id=t['dcid'], name=t['name'], abbreviation=t['abbreviation'], firstday=t['firstday'], lastday=t['lastday'], school=school))    
        session.commit()

    
    school_days = client.calendar_days(min(start_dates), max(end_dates), school.ps_id)
    bell_schedule_ids = list(set([day['bell_schedule_id'] for day in school_days]))
    for bsid in bell_schedule_ids:
        schedules[schoolid].setdefault(bsid, {})
    for day in school_days:
        logger.info(day['date_value'])
        date_values = day['date_value'].split("-")
        schoolday = session.query(SchoolDay).filter_by(date_value=datetime.Date(date_values[0], date_values[1], date_values[2])).first()
        if not schoolday:
            schoolday = SchoolDay(date_value=day['date_value'], date=datetime.Date(date_values[0], date_values[1], date_values[2]), bell_schedule_id=day['bell_schedule_id'], bs_name=day['bs_name'], school=school)
        else:
            schoolday = session.merge(SchoolDay(id=schoolday.id, date_value=day['date_value'], date=datetime.Date(date_values[0], date_values[1], date_values[2]), bell_schedule_id=day['bell_schedule_id'], bs_name=day['bs_name'], school=school))
        session.commit()
        
        for t in psterms:
            if day['date_value'] < t['firstday'] or day['date_value'] > t['lastday']:
                continue
            schedules[schoolid][day['bell_schedule_id']].setdefault(t['dcid'], {})
            if not schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                schedules[schoolid][day['bell_schedule_id']][t['dcid']] = client.section_meetings(t['dcid'], schoolid, day['bell_schedule_id'])
                calls += 1
            else:
                saved_calls += 1
                logger.info(f"found meeting, calls: {calls}, saved: {saved_calls}")

            for meeting in schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                if not meeting:
                    continue
                meet = session.query(Meeting).filter_by(start_time=int(meeting['start_time']), end_time=int(meeting['end_time'])).first()
                if not meet:
                    meet = Meeting(start_time=int(meeting['start_time']), end_time=int(meeting['end_time']))
                else:
                    meet = session.merge(Meeting(id=meeting.id, start_time=int(meeting['start_time']), end_time=int(meeting['end_time'])))
                meet.dates.append(schoolday)
                meet.terms.append(session.query(Term).filter_by(ps_id=t['dcid']).first())
                """    
                 x   teacher_email = Column(String)
                 x   teacher = Column(String)
                    id = Column(Integer, primary_key=True)
                    ps_dcid = Column(Integer)
                    term_name = Column(String)
                    school_id = Column(Integer, ForeignKey('schools.id'))
                    room = Column(String)
                    no_of_students = Column(Integer)
                  x  course = Column(String)
                    period_number = Column(Integer)
                  x  period_abbreviation = Column(String)
                    school = relationship('School', back_populates='sections')
                    meetings = relationship('Meeting', back_populates='section')
                """
                section = session.query(Section).filter_by(ps_id=meeting['section_dcid']).first()
                if not section:
                    section = Section(period_number = int(meeting['ps_dcid=meeting['section_dcid'],  period_abbreviation=meeting['period_abbreviation'], course=meeting['course_name'], teacher=meeting['lastfirst'], teacher_email=meeting['teacher_email'])
                else:
                    section = session.merge(Section(id=section.id, ps_id=meeting['section_dcid'], name=meeting['section_name'], course=meeting['course_name'], teacher=meeting['teacher_name']))

                session.commit()


                # roster = client.roster(meeting)
                meeting['firstday'] = t['firstday']
                meeting['lastday'] = t['lastday']
                meet = {'date': day['date_value'], 'bell_schedule': day['bs_name'], 'school': school_abbreviation}
                for k in ['start_time', 'end_time', 'term_name']:
                        meet[k] = meeting[k]
                section_events.setdefault(meeting['section_dcid'], meeting)
                section_events[meeting['section_dcid']].setdefault('meetings', [])
                section_events[meeting['section_dcid']]['meetings'].append(meet)
    for dcid, section in section_events.items():
        for k in ['start_time', 'end_time']:
                section.pop(k)
        return section_events

    # Commit the changes
    session.commit()

    # Query data as needed



if __name__ == "__main__":
            