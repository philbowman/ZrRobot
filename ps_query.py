from pypypowerschool import Client as PSClient
import datetime, json, os
from my_retry import *
from secrets_parameters import ps_url, client_id, client_secret
from logdef import *
from runtimer import *



class Query:
    def __init__(self):
        self.client = PSClient(ps_url, client_id, client_secret, 300)

    @my_retry
    def call(self, query_name, parameters):
        logger.info(query_name)	
        response = remove_dupes(self.client.powerquery(query_name, parameters))
        logger.debug(response)
        return response

    def assignments(self, sectiondcid):
        query_name = "/ws/xte/section/assignment/"
        p = {
            "section_ids": sectiondcid
        }
        assignments = self.client.powerquery(query_name, p)
        return assignments

    def district_cycle_days(self, yearid_in=None):
        if not yearid_in:
            yearids = self.yearid()
        else:
            yearids = [yearid_in]

        query_name = "/ws/schema/query/com.pearson.core.calendar.district_cycle_days"
        cycle_days = []
        for yearid in yearids:
            p = {
                "yearid": yearid
            }
            cd = self.call(query_name, p)
            print(cd)
            cycle_days += cd
        return cycle_days
    
    def calendar_days(self, start_date, end_date, schoolid):
        query_name = "/ws/schema/query/" + "headsup_calendar_days"
        p = {
            "school_id_in": schoolid,
            "start_date": start_date,
            "end_date": end_date
        }
        calendar_days = self.call(query_name, p)
        return calendar_days

    def blocks(self, calendar_day_dcid_in, schoolid):
        query_name = "/ws/schema/query/" + "headsup_blocks"
        p = {
            
                "calendar_day_dcid_in": calendar_day_dcid_in,
                "school_id": schoolid
        }
        blocks = self.call(query_name, p)
        return blocks

    def section_meetings(self, termdcid, schoolid, bell_schedule_id, cycle_day_letter=None):
        query_name = "/ws/schema/query/" + "headsup_section_meetings"
        p = {
            
                "schoolid": schoolid,
                "termdcid": termdcid,
                "bell_schedule_id": bell_schedule_id
        }
        section_meetings = self.call(query_name, p)
        if cycle_day_letter:
            return [s for s in section_meetings if cycle_day_letter == s['cycle_day_letter']]
        return section_meetings
    
    def roster(self, event):
        query_name = "/ws/schema/query/" + "headsup_roster"

        p = {
            "section_dcid": event['section_dcid']
        }
        roster = self.call(query_name, p)
        return roster

    def yearid(self, currentdate=None):
        if not currentdate:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            date = currentdate
        # print(date)
        query_name = "/ws/schema/query/" + "com.pearson.core.terms.yearid"
        p = {
        "schoolid": 0,
        "currentdate": date
        }
        yearids = self.call(query_name, p)
        # print(yearids)
        if not yearids:
            return []
        return [y['yearid'] for y in yearids]

    def terms(self, date, schoolid):
        #get the yearid
        yearids = self.yearid(date)
        terms = []
        for yearid in yearids:
            #get the terms for the year
            query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
            p = {
            "schoolid": schoolid,
            "yearid": yearid
            }
            term = self.call(query_name, p)
            for t in term:
                t['yearid'] = yearid
            terms += term
        return terms

    def termdcids(self, date, schoolid):
        #get the yearid
        yearids = self.yearid(date)

        #get the terms for the year
        terms = []
        for yearid in yearids:
            query_name = "/ws/schema/query/" + "com.pearson.core.terms.year_terms"
            p = {
            "schoolid": schoolid,
            "yearid": yearid
            }
            
            terms += self.call(query_name, p)
        termdcids = []
        for t in terms:
            if t['firstday'] <= date and t['lastday'] >= date:
                termdcids.append(t['dcid'])
        return termdcids

def remove_dupes(l):
    seen = set()
    new_l = []
    for d in l:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
        else:
            logger.debug("removed dupe: " + str(d))

    return new_l

class PSQuery(Query):

    @classmethod
    def list_bell_schedules(cls, schools, date=None, pull=False):
        if not pull:
            return cls.pull_bs_from_json()
        section_events = {}
        client = cls()
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        # schools = {hs_schoolid: "HS", ms_schoolid: "MS"}
        terms = {}
        start_dates = []
        end_dates = []
        schedules = {}
        day_schedules = {}
        for schoolid, school_abbreviation in schools.items():
                schedules.setdefault(schoolid, {})
                day_schedules.setdefault(schoolid, {})
                psterms = client.terms(date, schoolid)
                for t in psterms:
                    terms[t['dcid']] = t['abbreviation']
                    start_dates.append(t['firstday'])
                    end_dates.append(t['lastday'])
                school_days = client.calendar_days(min(start_dates), max(end_dates), schoolid)
                
                
                for day in school_days:
                    day_schedules[schoolid].setdefault(day['date_value'], {})
                    schedules[schoolid].setdefault(day['bell_schedule_id'], {})
                    logger.info(day['date_value'])
                    
                    meetings = cls.list_section_events(schools, pull=False, schedule=True)
                    try:
                        school_meetings = meetings[schoolid]
                    except KeyError:
                        school_meetings = meetings[str(schoolid)]
                    for termid, meeting in school_meetings[day['bell_schedule_id']].items():
                        for meet in meeting:
                            # schedules
                            schedules[schoolid][day['bell_schedule_id']].setdefault(meet['section_meeting'], {})
                            schedules[schoolid][day['bell_schedule_id']][meet['section_meeting']].setdefault(meet['period_abbreviation'], ())
                            schedules[schoolid][day['bell_schedule_id']][meet['section_meeting']][meet['period_abbreviation']] = (meet['start_time'], meet['end_time'])
                            day_schedules[schoolid][day['date_value']].setdefault(meet['section_meeting'], {})
                            day_schedules[schoolid][day['date_value']][meet['section_meeting']].setdefault(meet['period_abbreviation'], {})
                            day_schedules[schoolid][day['date_value']][meet['section_meeting']][meet['period_abbreviation']] = (meet['start_time'], meet['end_time'])

        with open('day_schedules.json', 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(day_schedules, indent=4))

        with open('bell_schedules.json', 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(schedules, indent=4))
        return (schedules, day_schedules)

    @classmethod
    def list_section_events(cls, schools, date=None, pull=False, schedule=False):
        if not pull:
            return cls.pull_from_json(schedule)
        section_events = {}
        client = cls()
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        # schools = {hs_schoolid: "HS", ms_schoolid: "MS"}
        terms = {}
        start_dates = []
        end_dates = []
        schedules = {}
        saved_calls = 0
        for schoolid, school_abbreviation in schools.items():
                schedules.setdefault(schoolid, {})
                psterms = client.terms(date, schoolid)
                for t in psterms:
                    terms[t['dcid']] = {
                        'abbreviation': t['abbreviation'],
                        'start_date': t['firstday'],
                        'end_date': t['lastday'],
                        'yearid': t['yearid']
                    }
                    start_dates.append(t['firstday'])
                    end_dates.append(t['lastday'])
                
                year_startdate = min(start_dates)
                year_enddate = max(end_dates)
                for t_dcid, t in terms.items():
                    t['year_firstday'] = year_startdate
                    t['year_lastday'] = year_enddate
                    t['year_abbreviation'] = f"{year_startdate[-2:]}-{year_enddate[-2:]}"

                school_days = client.calendar_days(min(start_dates), max(end_dates), schoolid)
                bell_schedule_ids = list(set([day['bell_schedule_id'] for day in school_days]))
                for bsid in bell_schedule_ids:
                    schedules[schoolid].setdefault(bsid, {})
                for day in school_days:
                    logger.info(day['date_value'])
                    for t in psterms:
                        if day['date_value'] < t['firstday'] or day['date_value'] > t['lastday']:
                            continue
                        schedules[schoolid][day['bell_schedule_id']].setdefault(t['dcid'], {})
                        if not schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                            schedules[schoolid][day['bell_schedule_id']][t['dcid']] = client.section_meetings(t['dcid'], schoolid, day['bell_schedule_id'])
                        else:
                            saved_calls += 1
                            logger.info(f"found meeting, saved {saved_calls}")

                        for meeting in schedules[schoolid][day['bell_schedule_id']][t['dcid']]:
                            # roster = client.roster(meeting)
                            meet = {'term_dcid': t['dcid'], 'date': day['date_value'], 'bell_schedule': day['bs_name'], 'school': school_abbreviation}
                            for k in ['start_time', 'end_time', 'term_name', 'cycle_day_letter', 'period_abbreviation', 'period_number']:
                                meet[k] = meeting[k]
                            section_events.setdefault(meeting['section_dcid'], meeting)
                            section_events[meeting['section_dcid']].setdefault('term_dcids', [])
                            if meet['term_dcid'] not in section_events[meeting['section_dcid']]['term_dcids']:
                                section_events[meeting['section_dcid']]['term_dcids'].append(meet['term_dcid'])
                            section_events[meeting['section_dcid']].setdefault('meetings', [])
                            section_events[meeting['section_dcid']]['meetings'].append(meet)
                        
        with open('terms.json', 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(terms, indent=4))

        with open('schedules.json', 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(schedules, indent=4))

        with open('section_events.json', 'w', encoding='utf-8') as jsonf:
            jsonf.write(json.dumps(section_events, indent=4))
        if schedule:
            return schedules
        return (section_events, terms)

    @staticmethod
    def pull_bs_from_json():
        if not os.path.exists('bell_schedules.json'):
             logger.warning("schedules.json not found; run list_bell_schedules(pull=True)")
             return {}
        with open('bell_schedules.json', 'r', encoding='utf-8') as jsonf:
            schedules = json.loads(jsonf.read())
        return schedules

    @staticmethod
    def pull_from_json(schedule):
        if schedule:
            if not os.path.exists('schedules.json'):
                 logger.warning("schedules.json not found; run list_section_events(pull=True)")
                 return {}
            with open('schedules.json', 'r', encoding='utf-8') as jsonf:
                schedules = json.loads(jsonf.read())
            return schedules
        

        if not os.path.exists('section_events.json'):
             logger.warning("section_events.json not found; run list_section_events(pull=True)")
             return {}
        if not os.path.exists('terms.json'):
            logger.warning("terms.json not found; run list_section_events(pull=True)")
            return {}
        with open('section_events.json', 'r', encoding='utf-8') as jsonf:
            section_events = json.loads(jsonf.read())
        with open('terms.json', 'r', encoding='utf-8') as jsonf:
            terms = json.loads(jsonf.read())
        return (section_events, terms)
