import copy
from enum import Enum
import math

survival_probability = (0.052, 0.089, 0.15, 0.23, 0.35, 0.49, 0.63, 0.75, 0.84, 0.9, 0.94, 0.97, 0.98)
care_time = (180, 170, 160, 150, 140, 130, 120, 110, 90, 60, 50, 40, 30)
deterioration = ((0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 (4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0),
                 (6, 5, 4, 3, 2, 1, 0, 0, 0, 0, 0, 0),
                 (8, 7, 6, 5, 4, 3, 2, 1, 0, 0, 0, 0),
                 (9, 8, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0),
                 (10, 9, 9, 8, 8, 7, 6, 6, 5, 5, 4, 4),
                 (11, 11, 10, 10, 9, 8, 8, 7, 7, 6, 6, 5),
                 (12, 12, 11, 11, 10, 10, 10, 10, 9, 9, 8, 8))


class RPM:

    def __init__(self, _id):
        """
        class that represent a rpm function
        :param _id: the rpm id (0 - 12)
        :rtype int
        :param survival: the init survival probability for this rpm
        :rtype float
        :param triage: the init triage classification
        :rtype Triage
        :param care_time: the init care time
        :rtype float
        :param time_to_survive: the init time to survive
        :rtype float
        :param uploading_time: the time
        """
        self._id = _id
        self.triage = triage_by_rpm(_id)
        self.survival = self.get_survival()
        self.care_time = self.get_care_time()
        self.time_to_survive = self.get_time_to_survive()
        self.uploading_time = self.get_uploading_time()

    def get_survival(self):
        return round(survival_probability[self._id], 2)

    def get_care_time(self, rpm=None):
        if rpm is None: rpm = self._id
        return round(care_time[rpm] * 0.7, 2)

    def get_uploading_time(self, rpm=None):
        if rpm is None: rpm = self._id
        return round(care_time[rpm] * 0.3, 2)

    def get_time_to_survive(self, rpm=None):
        if rpm is None:
            rpm = self._id
        try:
            index = deterioration[rpm].index(0)
        except:
            return self.get_time_to_survive(deterioration[self._id][11])
        else:
            return index * 30

    def get_survival_by_time_deterioration(self, time=0, relative_rpm=None):
        if relative_rpm is None:
            relative_rpm = self._id
        if time > 360:  # if time is more than 360, go to last rpm function
            return self.get_survival_by_time_deterioration(time - 360, deterioration[relative_rpm][360 // 30 - 1])
        rpm1, rpm2 = self.get_rpms_by_time(time, relative_rpm)
        slope = self.slope(rpm1, rpm2)
        survival = survival_probability[rpm1] + (time % 30) * slope
        return round(survival, 3)

    def get_survival_potential_by_time(self, time):
        return max(self.get_survival_by_time_deterioration(time) -
                   self.get_survival_by_time_deterioration(time+360), 0.052)

    def get_rpms_by_time(self, time, relative_rpm=None):
        """

        :param time: the time for the rpm
        :param relative_rpm: used only in recursion
        :return: int, int
        """
        if relative_rpm is None:
            relative_rpm = self._id
        if time >= 360:  # if time is more than 360, go to last rpm function
            return self.get_rpms_by_time(time - 360, deterioration[relative_rpm][360 // 30 - 1])

        else:
            quotient, remainder = divmod(time, 30)
            if quotient > 12:
                print('here is my bug')
            if quotient == 0:
                return copy.copy(relative_rpm), copy.copy(relative_rpm)
            return deterioration[relative_rpm][int(quotient-1)], deterioration[relative_rpm][int(quotient)]

    def get_rpm_by_time(self, time):
        return RPM(self.get_rpms_by_time(time)[0])

    def get_triage_by_time(self, time):
        return triage_by_rpm(self.get_rpms_by_time(time)[1])

    def slope(self, rpm1=0, rpm2=0):
        """
        calc the slope for the function between rmp1 and 2
        :param rpm1: the rpm before the time
        :param rpm2: the rpm ufter the time
        :return: slope
        :rtype float
        """
        if rpm1 == rpm2:
            return 0
        return (survival_probability[rpm1] - survival_probability[rpm2]) / (0 - 30)

    def get_care_by_time(self, time):
        rpm = self.get_rpms_by_time(time)[1]
        return self.get_care_time(rpm)

    def get_uploading_by_time(self, time):
        rpm = self.get_rpms_by_time(time)[1]
        return self.get_uploading_time(rpm)

    def get_id(self):
        return self._id

    def __str__(self):
        return str(self._id)



def triage_by_rpm(rpm):
    if rpm <= 6:
        return 'URGENT'
    elif 6 < rpm <= 9:
        return 'MEDIUM'
    else:
        return 'NON_URGENT'




class Triage(Enum):
    NON_URGENT = 0
    MEDIUM = 1
    URGENT = 2
