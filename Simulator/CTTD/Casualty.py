from Simulator.CTTD.RPM import RPM
import copy

dbug = True

class Casualty:
    def __init__(self, init_RPM=12, t_born=0, _id=0, disaster_site_id=0):
        """
        :type init_RPM: int
        :type t_born: float
        :type _id: int
        :type disaster_site_id: int

        """
        self.disaster_site_id = disaster_site_id
        self._id = _id
        self._t_born = t_born
        self._init_RPM = RPM(init_RPM)
        self.triage = self._init_RPM.triage
        self.current_RPM = self._init_RPM
        self.activities = ('treatment', 'uploaded', 'transportation')
        self.scheduled_activities = {k: None for k in self.activities}  # activity: [rpm_at_start_time, start_time,duration](float)
        self.preformed_activities = {k: None for k in self.activities}  # activity: [start_time,duration](float)
        self.scheduled_status = 'waiting'
        self.preformed_status = 'waiting'
        self.last_update_time = self._t_born
        self.finite_survival = None
        self.last_schedule_time = self._t_born

    # updated performances

    def update_performances_activities(self,activity, start_time, transportation_time =None):
        # determine the current rpm to be the next rpm (round by the modulo)
        rpm_min, rpm_max = self.current_RPM.get_rpms_by_time(start_time - self.last_update_time)
        if start_time % 30 < 15:
            self.current_RPM = RPM(rpm_min)
        else:
            self.current_RPM = RPM(rpm_max)

        match activity:
            case 'treatment':
                self.preformed_status = 'receive treatment'
                time = self.current_RPM.get_care_time()
            case 'uploaded':
                self.preformed_status = 'uploaded'
                time = self.current_RPM.get_uploading_time()

            case 'transportation':
                self.finite_survival = self.current_RPM.get_survival_by_time_deterioration(
                    start_time - self.last_update_time)
                time = transportation_time
                self.preformed_status = 'evacuated'
        self.preformed_activities[activity] = [start_time, time]
        self.last_update_time = start_time + time  # last update time is after performance

    def receive_treatment(self, start_time):
        self.update_performances_activities(activity='treatment', start_time=start_time)

    def uploaded(self, start_time):
        self.update_performances_activities(activity='uploaded', start_time=start_time)

    def evacuated(self, start_time, transportation_time):
        self.update_performances_activities(activity='transportation', start_time=start_time,
                                            transportation_time=transportation_time)

    # updated schedule
    def schedule_activity(self, activity, start_time, transportation_time):

        rpm_min, rpm_max = self.current_RPM.get_rpms_by_time(start_time - self.last_update_time)
        if start_time % 30 < 15:
            rpm = RPM(rpm_min)
        else:
            rpm = RPM(rpm_max)

        match activity:
            case 'treatment':
                self.scheduled_status = 'receive treatment'
                time = rpm.get_care_time()
            case 'uploaded':
                self.scheduled_status = 'uploaded'
                time = rpm.get_uploading_time()
            case 'transportation':
                time = transportation_time
                self.scheduled_status = 'evacuated'
        self.last_schedule_time = start_time + time
        self.scheduled_activities[activity] = [rpm, start_time, time]

    # return the survival by a given time and the activities performance
    def get_survival_by_time_and_performance(self, time=None):
        if time is None: time = self.t_born
        self.current_RPM.get_survival_by_time_deterioration(time - self.last_update_time)

    # return the survival by a given time and the activities scheduled
    def get_survival_by_time_and_schedule(self, time=None):
        if time is None: time = self.t_born
        temp_rpm, idle_time = self.rmp_and_idle_time_by_schedule(time)
        RPM(temp_rpm).get_survival_by_time_deterioration(idle_time)

    def rmp_and_idle_time_by_schedule(self, time):
        """
        reduce the care time from the
        :param time: a time to calculate the rpm of the casualty and the idle time
        :return:
        """
        idle_time = time - self.last_schedule_time
        for activity in self.scheduled_activities.keys():
            rpm = self.scheduled_activities[activity][1]
        return idle_time, rpm

    def survival_by_time(self, time):
        return self.current_RPM.get_survival_by_time_deterioration(time)

    def get_triage_by_time(self, time):
        return self.current_RPM.get_triage_by_time(time)

    def get_potential_survival_by_start_time(self, time):
        return self.current_RPM.get_survival_potential_by_time(time)

    def get_care_time(self, skill, time):
        if skill == 'treatment':
            return self.current_RPM.get_care_by_time(time)
        elif skill == 'uploading':
            return self.current_RPM.get_uploading_by_time(time)
        else:
            return 0.1

    def get_id(self):
        return copy.copy(self._id)

    def get_triage(self):
        return self.get_triage_by_time(self.last_update_time)

    def __eq__(self, other):
        return self._id == other._id

    def __str__(self):
        return 'Id: '+str(self._id) + ' RPM: '+str(self._init_RPM) + ' schedule status: ' + self.scheduled_status \
               + ' preformed status: ' + self.preformed_status

    def __hash__(self):
        return self._id
