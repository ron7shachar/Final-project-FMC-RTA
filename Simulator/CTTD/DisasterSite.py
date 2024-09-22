import copy
from abc import ABC
from bisect import insort
from collections import deque
from bisect import insort_left
from random import random
from functools import cmp_to_key

from Simulator.CTTD.Casualty import Casualty
from Simulator.SimulationComponents import ServiceRequester, get_skill_amount_dict

from Simulator.CTTD.MedicalUnit import *
from collections import Counter

dbug = True


def update_offers_times(allocated_offers):
    for skill in allocated_offers.keys():
        for offer in allocated_offers[skill]:
            if len(offer.mission) == 0:
                offer.max_capacity = 0
                offer.amount = 0
                offer.duration = 0
            else:
                offer.amount = len(offer.mission)
                offer.arrival_time = min(d['arrival_time'] for d in offer.mission)
                offer.leaving_time = max(d['leaving_time'] for d in offer.mission)
                offer.duration = offer.leaving_time - offer.arrival_time


def dict_minimum_amount(skills_dict, casualties_dict):
    cas_skills = {skill: 0 for skill in skills_dict.keys()}
    for cas in casualties_dict.values():
        for skill in skills_dict.keys():
            if skill in skills_dict:
                cas_skills[skill] += 1
    skills_dict_minimum = {key: min(skills_dict[key], cas_skills[key]) for key in
                           skills_dict.keys() & cas_skills.keys()}
    return skills_dict_minimum


def capacity_per_provider(offers):
    providers = [offer for offer in offers if isinstance(offer, MedicalUnit)]
    dict_providers_capacities = {provider: copy(provider.current_capacity) for provider in providers}
    return dict_providers_capacities


def sort_casualties_by_threshold(casualties, time_arrival=None, threshold=0.4):
    if time_arrival is None:
        time_arrival = 0.0
        above_threshold = [x for x in casualties if x[0].survival_by_time(time_arrival) > threshold]
        below_threshold = [x for x in casualties if x[0].survival_by_time(time_arrival) <= threshold]
        below_threshold.sort(key=lambda x: x[0].survival_by_time(time_arrival))  # , reverse=True
        above_threshold.sort(key=lambda x: x[0].survival_by_time(time_arrival))
    elif time_arrival is not None:
        above_threshold = [x for x in casualties if x[0].survival_by_time(max(x[1], time_arrival)) > threshold]
        below_threshold = [x for x in casualties if x[0].survival_by_time(max(x[1], time_arrival)) <= threshold]
        below_threshold.sort(key=lambda x: x[0].survival_by_time(max(x[1], time_arrival))) #, reverse=True
        above_threshold.sort(key=lambda x: x[0].survival_by_time(max(x[1], time_arrival)))
    return above_threshold + below_threshold





def create_schedule_for_casualties(casualties_needed_activities_temp, schedules):
    """

    :param casualties_needed_activities_temp:
    :param schedules:
    :return: {casualty: {skill:time}}
    """
    casualties_with_times = {key: copy.copy(value) for key, value in casualties_needed_activities_temp.items()}
    for list_of_assignment in schedules.values():
        for assignment in list_of_assignment:
            for mission in assignment.mission:
                if assignment.skill not in casualties_with_times[mission['mission'].get_id()]:
                    casualties_with_times[mission['mission'].get_id()].append(
                        (assignment.skill, mission['arrival_time']))

                    # casualties_with_times[mission['mission'].get_id()][assignment.skill] = mission['arrival_time']
                else:
                    # casualties_with_times[mission['mission'].get_id()].append((assignment.skill, mission['arrival_time']))
                    casualties_with_times[mission['mission'].get_id()] = deque(
                        [(assignment.skill, mission['arrival_time'])
                         if x == assignment.skill else x for x in casualties_with_times[mission['mission'].get_id()]])

                    # casualties_with_times[mission['mission'].get_id()][assignment.skill] = mission['arrival_time']

    return casualties_with_times


class DisasterSite(ServiceRequester, ABC):

    def __init__(self, id_, skills, casualties=[], location=[0.0, 0.0], time_born=0.0, skills_weights={}):
        ServiceRequester.__init__(self, _id=id_, time_born=time_born, skills=skills, location=location)
        self.skill_weights = skills_weights
        self.casualties = []
        self.casualties_needed_activities = {}  # {casualties_id: [skills_activities]}
        self.add_casualties(casualties)
        self.near_hospital = [0.0, 0.0]  # updated later
        self.utility_threshold_for_acceptance = 0.0

    def add_casualties(self, casualties):
        self.casualties += casualties
        # create an ordered deque
        skill_deque = deque()
        from Simulator.CTTD.CttdSimulatorComponents import cmp_skills
        self.skills.sort(key=cmp_to_key(cmp_skills))
        skill_deque = deque(self.skills)
        # {casualties_id: [skills_activities]}
        self.casualties_needed_activities = {key.get_id(): copy.deepcopy(skill_deque) for key in self.casualties}
        self.calc_max_time()
        self.update_skills_requirements()
        self.update_max_util()

    def calc_max_time(self):
        self.max_time = max(self.casualties, key=lambda x: x.current_RPM.time_to_survive).current_RPM.time_to_survive

    def update_skills_requirements(self):
        self.skills_requirements = {item: sum(item in value for value in self.casualties_needed_activities.values())
                                    for item in self.skills}
        self.max_required = copy.deepcopy(self.skills_requirements)

    def update_max_util(self):
        casualties_amount = len(self.casualties)
        self.max_util = {skill: casualties_amount for skill in self.max_util}

    # 1- allocate offers to SPs
    def allocated_offers(self, skills_needed, offers_received_by_skill, allocation_version=0):
        """
        method that used by solver agents -
        :param allocation_version:
        :param skills_needed
        :type {skill: double}
        :param offers_received_by_skill
        :type {skill: (variableAssignment)}
        :return: {skill: set(variableAssignment)} , NCLO (int)
        """
        NCLO = 1
        allocated_offers = {}
        # sort skills_activities by activity
        from Simulator.CTTD.CttdSimulatorComponents import cmp_skills
        skills_needed = {k: skills_needed[k] for k in sorted(skills_needed.keys(), key=cmp_to_key(cmp_skills))}
        # activities to allocate {casualty_id: [deque, last time]}
        casualties_to_allocate = copy.deepcopy(self.casualties_needed_activities)
        casualties_to_allocate = {key: [value, 0.0] for key, value in casualties_to_allocate.items()}
        casualties_to_allocate = self.sort_casualties_by_potential_survival(casualties_to_allocate)
        if allocation_version == 3:
            offers_received_by_skill, casualties_to_allocate = self.remove_accepted_offers(offers_received_by_skill, casualties_to_allocate)
        # skill needed - minimum between casualties skills_activities and sent skill needed
        skills_needed = dict_minimum_amount(skills_needed, casualties_to_allocate)
        skills  = [k for k in self.skills if k in skills_needed]
        for skill in skills:
            allocated_offers[skill] = set()
            # all positive offers sorted by arrival time
            skill_offers_by_arrival = [offer for offer in offers_received_by_skill[skill] if
                                       offer.utility is not 0 and not offer.accept]
            skill_offers_by_arrival = list(sorted(skill_offers_by_arrival, key=lambda offer: offer.arrival_time))
            q = min(self.max_required[skill], len(skill_offers_by_arrival))
            # NCLO
            NCLO += super().number_of_comparisons(q, len(skill_offers_by_arrival))

            # copy all offers, reset and insert to dict
            offers_to_allocate = copy.copy(skill_offers_by_arrival[0:skills_needed[skill]])
            offers_skill_available_dict = get_skill_amount_dict(offers_to_allocate)  # {offer: [amount]}

            # all casualties that need this skill next [(casualty_id, last_time)]
            # for _, value in casualties_to_allocate.items():
            #     if not value[0]:
            #         print('bug')
            casualties_needed_skill = [(cas, value[1]) for cas, value in casualties_to_allocate.items() if
                                       value[0][0] == skill]
            # all offers capacities
            capacities = {} # offer_p_id : capacity
            # while more casualties to allocate and offers available
            while offers_skill_available_dict:

                if len(casualties_needed_skill) <=0:
                    break

                # order offers by next skill unit work start
                offers_skill_available_dict = dict(sorted(offers_skill_available_dict.items(),
                                                          key=lambda offer: (offer[0].arrival_time, offer[0].provider))) # todo add equle breake by provider id
                # NCLO
                NCLO += super().number_of_comparisons(1, len(offers_skill_available_dict))
                # the next offer to allocate
                offer_stats = next(iter(offers_skill_available_dict.items()))
                if offer_stats[0].provider not in capacities:
                    capacities[offer_stats[0].provider] = list(copy.copy(offer_stats[0].max_capacity))
                    offer_stats[0].max_capacity = 0
                offer_capacity = capacities[offer_stats[0].provider]


                # while provider have more skills to offer
                while offers_skill_available_dict.keys().__contains__(offer_stats[0])  and len(casualties_needed_skill) > 0:
                    next_casualty = None

                    if offer_capacity[1] > 0 and offer_stats[1][0] > 0:
                        # get next casualty - by t.a, next skill. and  agent capabilities
                        next_time = offer_stats[0].arrival_time
                        if len(offer_stats[0].mission) > 0:
                            next_time = offer_stats[0].mission[-1]['leaving_time']

                        next_casualty = self.next_casualty(copy.deepcopy(casualties_to_allocate), skill, next_time,
                                                               offer_capacity[0])
                        from Simulator.CTTD.CttdSimulatorComponents import get_skill_capacity_points
                        capacity_to_reduce = 0
                        if next_casualty is not None:
                            capacity_to_reduce = get_skill_capacity_points(
                            next_casualty[0].get_triage_by_time(0.0))

                        # if None - delete offer from available or not inof cap
                        if (next_casualty is None) or (offer_capacity[1] - capacity_to_reduce < 0):
                            del offers_skill_available_dict[offer_stats[0]]
                            offer_stats[0].amount = 0
                            break

                        else:
                            start_time = max(next_time, next_casualty[1])
                            duration = next_casualty[0].get_care_time(skill, start_time)
                            leaving_time = start_time + duration
                            offer_stats[0].mission.append({'mission': next_casualty[0], 'arrival_time': start_time,
                                                           'duration': duration, 'leaving_time': leaving_time})

                            # allocate- update amount, mission, and calc time
                            offer_stats[0].amount += 1
                            offer_stats[1][0] -= 1

                            # remove from needed
                            casualty_tuple_to_remove = next(
                                filter(lambda x: x[0] == next_casualty[0].get_id(), casualties_needed_skill), None)
                            casualties_needed_skill.remove(casualty_tuple_to_remove)
                            casualties_to_allocate[next_casualty[0].get_id()][0].popleft()
                            casualties_to_allocate[next_casualty[0].get_id()][1] = leaving_time
                            if not casualties_to_allocate[next_casualty[0].get_id()][0]:
                                del casualties_to_allocate[next_casualty[0].get_id()]


                            # update provider
                            # providers_next_time[offer_stats[0].provider] = leaving_time

                            # capacities[offer_stats[0].provider][1] -= capacity_to_reduce
                            offer_stats[0].max_capacity += capacity_to_reduce
                            offer_stats[0].arrival_time = leaving_time
                            offer_capacity[1] -= capacity_to_reduce
                            break
                    elif offer_capacity[1] <= 0 or offer_stats[1][0] <= 0:
                        del offers_skill_available_dict[offer_stats[0]]
                        offer_stats[0].amount = 0

                if offer_stats[0] not in allocated_offers[skill] and len(offer_stats[0].mission) > 0:
                    allocated_offers[skill].add(offer_stats[0])
                    # if offers_skill_available_dict.__contains__(offer_stats[0]):
                    #     del offers_skill_available_dict[offer_stats[0]]

        update_offers_times(allocated_offers)
        return allocated_offers, NCLO

    def sort_casualties_by_potential_survival(self, casualties_by_id):
        casualties = {cas: casualties_by_id[cas.get_id()] for cas in self.casualties for i in
                      casualties_by_id.keys() if cas.get_id() == i}  # (casualty, last_time_update)

        sorted_casualties = dict(sorted(casualties.items(), key=lambda x: x[0].get_potential_survival_by_start_time(0.0),
                                        reverse=True))
        sorted_casualties = {cas.get_id(): value for cas, value in sorted_casualties.items()}
        return sorted_casualties

    def remove_accepted_offers(self, offers_received_by_skill, casualties_to_allocate):
        for skill, offers in offers_received_by_skill.items():
            for offer in offers:
                if offer.accept:
                    for mission in offer.mission:
                        casualties_to_allocate[mission['mission'].get_id()][0].remove(skill)
            offers[:] = [offer for offer in offers if not offer.accept]
            casualties_to_allocate = {cas_id: value for cas_id, value in casualties_to_allocate.items() if value[0]}

        return offers_received_by_skill, casualties_to_allocate

    def reduce_skill_requirement(self, service, current_time):
        skills_received = 0
        for mission_dict in service.mission:
            if mission_dict['leaving_time'] <= current_time:
                self.casualties_needed_activities[mission_dict['mission'].get_id()].popleft()
                if service.skill == 'treatment':
                    mission_dict['mission'].receive_treatment(mission_dict['arrival_time'])
                elif service.skill == 'uploading':
                    mission_dict['mission'].uploaded(mission_dict['arrival_time'])
                elif service.skill == 'transportation':
                    mission_dict['mission'].uploaded(mission_dict['arrival_time'])
                    del self.casualties_needed_activities[mission_dict['mission'].get_id()]
                service.last_workload_used = mission_dict['leaving_time']
                self.skills_requirements[service.skill] -= 1
                skills_received += 1
        return skills_received

    def get_next_casualty(self, casualties_by_id, arrival_time, agent_capabilities, initial_triage_time=True):
        """
        :param casualties_by_id:  [(cas_id,last_update_time)]
        :param arrival_time: the time that the SP arrived to the disaster site
        :param agent_capabilities: {triage: max_workload}
        :param initial_triage_time: True - the triage of the casualty is relatve to the max time
                                    False - the triage is relative to current casualty RPM
        :return:
        """
        casualties = [(cas, max(arrival_time, time)) for cas in self.casualties for i, time in
                      casualties_by_id if cas.get_id() == i]  # (casualty, last_time_update)

        #[(casualty, next_time)]
        # sorted_casualties = sort_casualties_by_threshold(casualties, threshold=0.4)
        # sorted_casualties = sort_casualties_by_threshold(casualties, arrival_time, threshold=0.4)
        sorted_casualties = sorted(casualties, key=lambda x: x[0].get_potential_survival_by_start_time(0.0),
                                   reverse=True)

        for cas in sorted_casualties:
            triage = None
            if initial_triage_time:
                triage = cas[0].get_triage_by_time(max(cas[1], arrival_time))
            else:
                triage = cas[0].get_triage()

            workload = 0
            if triage in agent_capabilities.keys():
                workload = agent_capabilities[triage]
            if workload > 0:
                return cas
        return None

    def next_casualty(self, casualties_by_id, skill, arrival_time, agent_capabilities):

        for cas, value in casualties_by_id.items():
            casualty = self.get_casualty_by_id(cas)
            triage = casualty.get_triage()
            workload = 0
            if triage in agent_capabilities.keys() and value[0][0] == skill:
                workload = agent_capabilities[triage]
            if workload > 0:
                return [casualty, max(arrival_time, value[1])]
        return None

    @staticmethod
    def create_provider_next_time(offers):
        new_dict = {}
        for skill, offers in offers.items():
            for offer in offers:
                provider = offer.provider
                time = offer.arrival_time
                skill = offer.skill
                if provider not in new_dict and skill == 'treatment':
                    new_dict[provider] = round(time, 2)
                # else:
                #     new_dict[provider] = min(new_dict[provider], time)
        return new_dict

    def get_casualty_by_id(self, cas_id):
        return next((casualty for casualty in self.casualties if casualty.get_id() == cas_id), None)

    # 2 - calculate final utility by current scheduled SPs view
    def final_utility(self, allocated_offers, SP_view=None, utility_version=0, cost=True, simulation_times=None):
        """

        :param allocated_offers:
        :param SP_view:
        :param utility_version: the utility version - if 0 - above 0.4, 1 - sampling from uniform distribution
        cost: if true - calculate the cost of the final
        :return:
        """
        final_utility = len(self.casualties)
        if SP_view is None:
            schedules = allocated_offers
        else:
            schedules = super().create_schedules_by_skill_by_SP_view(SP_view)  # {skill: [v.a]}
        # casualties scheduled by SP_view
        casualties_schedule = create_schedule_for_casualties(copy.deepcopy(self.casualties_needed_activities),
                                                             schedules)
        # casualties with their survival probability by schedule {cas: prop}
        casualties_survival_dict = self.create_survival_dict_by_schedule(copy.deepcopy(casualties_schedule))
        casualties_potential_dict = self.create_survival_potential_by_schedule(casualties_schedule)
        if utility_version == 0:
            count = sum(1 for value in casualties_survival_dict.values() if value > 0.4)

        elif utility_version == 1:
            count = sum(1 for value in casualties_survival_dict.values if random.random() < value)

        # if dbug:
        #     for cas, survival in casualties_survival_dict.items():
        #         print("cas id" + str(cas.get_id()) + " survival: " + str(survival))


        final_utility -= count
        if cost:
            return final_utility
        else:
            if len(casualties_survival_dict) > 0:
                return functools.reduce(lambda x, y: x+y, casualties_potential_dict.values())
            else:
                return 0

    def calc_simple_bid(self, offer):
        bid = 0
        only_the_sp_offer = {offer.skill: [offer]}
        skills_needed_temp = {offer.skill: self.skills_requirements[offer.skill]}
        only_sp_allocated_offers, _ = self.allocated_offers(skills_needed_temp, only_the_sp_offer)
        utility_simple = self.final_utility(only_sp_allocated_offers, cost=False)
        bid = utility_simple
        return round(max(0, bid), 2)

    def calc_truncated_bids(self, offers, util_j, GS_accepted_providers, neighbors):
        skill_needed ={}
        for skill in offers:
            to_keep = []
            for offer in offers[skill]:
                if self.is_provider_needed(offer.max_capacity[0], offer.arrival_time, offer.skill):
                    to_keep.append(offer)
                else:
                    util_j[skill][offer.provider] = 0
            offers[skill] = to_keep
            skill_needed[skill] = self.skills_requirements[skill]

        self.offers_that_where_allocated = {}
        NCLO = 0
        allocated_offers, NCLO = self.allocated_offers(copy.deepcopy(skill_needed), offers)
        self.offers_that_where_allocated = allocated_offers

        for skill in allocated_offers:
            for offer in allocated_offers[skill]:
                offer_to_sent = {skill:[offer]}
                util = self.final_utility(offer_to_sent, cost = False)
                if util >= self.utility_threshold_for_acceptance and skill in util_j.keys():
                    util_j[offer.skill][offer.provider] = util
        return NCLO
    def create_survival_dict_by_schedule(self, casualties_schedule):
        """
        :param casualties_schedule: {cas_id:{skill:start_time}}
        :return: {cas: survival probability}
        """
        casualties_survival_prob = {}
        # simulation of survival probability for each cas
        for casualty_id in casualties_schedule:
            casualty = self.get_casualty_by_id(casualty_id)
            current_RPM = copy.copy(casualty.current_RPM)
            last_update_time = copy.copy(casualty.last_update_time)
            schedule = casualties_schedule[casualty_id]
            care_time = 0
            while schedule:
                if type(schedule[0]) is tuple:

                    skill, time = schedule.popleft()
                    last_update_time = round(time - care_time, 2)

                else:
                    break
                current_RPM = current_RPM.get_rpm_by_time(last_update_time)
                care_time = casualty.get_care_time(skill, last_update_time)

                # todo - all activities? if len(schedule) == 3
                survival_probability = current_RPM.get_survival_by_time_deterioration()
                casualties_survival_prob[casualty] = survival_probability
                break
        return casualties_survival_prob

    def create_survival_potential_by_schedule(self, casualties_schedule):
        """
       :param casualties_schedule: {cas_id:{skill:start_time}}
       :return: {cas: survival potential}
       """
        casualties_survival_potential = {}
        # simulation of survival probability for each cas
        for casualty_id in casualties_schedule:
            casualty = self.get_casualty_by_id(casualty_id)
            current_RPM = copy.copy(casualty.current_RPM)
            last_update_time = copy.copy(casualty.last_update_time)
            schedule = casualties_schedule[casualty_id]
            care_time = 0
            while schedule:
                if type(schedule[0]) is tuple:

                    skill, time = schedule.popleft()
                    last_update_time = round(time - care_time, 2)

                else:
                    break
                current_RPM = current_RPM.get_rpm_by_time(last_update_time)
                survival_potential = current_RPM.get_survival_potential_by_time(0.0)
                care_time = casualty.get_care_time(skill, last_update_time)
                casualties_survival_potential[casualty] = survival_potential
                break
        return casualties_survival_potential


    def calc_converge_bid_to_offer(self, skill, offer):
        """
        :param skill:
        :param offer:
        :param bid_type:
        :return: bid for the offer
        """

        bid = 0
        if len(offer.mission) > 0:

            # minimum_cas = max(offer.mission, key=lambda x:
            # x['mission'].survival_by_time(x['arrival_time']))

            # bid = round(minimum_cas['mission'].survival_by_time(
            #     minimum_cas['arrival_time']), 2)

            minimum_cas = min(offer.mission, key=lambda x:
            x['arrival_time'])

            bid = round(minimum_cas['mission'].get_potential_survival_by_start_time(0.0), 2)

        return round(max(0,bid),2)

    def get_care_time(self,skill,time):
        ans=math.inf
        for cas in self.casualties:
            if ans > cas.get_care_time(skill, time):
                ans = cas.get_care_time(skill, time)
        return ans

    def update_cap(self, skill, workload):
        if self.max_required[skill] > workload:
            self.max_required[skill] = workload

    def __deepcopy__(self, memodict={}):
        copy_object = DisasterSite(self.getId(), self.skills, copy.deepcopy(self.casualties),
                                   self.location, self.last_time_updated, self.skill_weights)
        copy_object.near_hospital = copy.deepcopy(self.near_hospital)
        return copy_object


    def is_offer_relevant_according_to_accepted_offers(self, offer, accepted_offers):
        needed_cas = copy.deepcopy(self.casualties_needed_activities)
        needed_cas = {key: [value, 0.0] for key, value in needed_cas.items()}

        for ac_offer in accepted_offers:
            for accepted_offer in self.offers_that_where_allocated[offer.skill]:
                if ac_offer.provider == accepted_offer.provider:
                    for mission in accepted_offer.mission:
                        if (mission['mission'].get_id() in self.casualties_needed_activities and
                                self.casualties_needed_activities[mission['mission'].get_id()][0] == accepted_offer.skill):
                            needed_cas[mission['mission'].get_id()][0].popleft()
        if self.next_casualty(needed_cas, offer.skill, offer.arrival_time,
                              offer.max_capacity[0]) is not None:
            return True
        else:
            return False
    def is_provider_needed(self, max_capacity, arrival_time, skill):
        casualties_to_allocate = copy.deepcopy(self.casualties_needed_activities)
        casualties_to_allocate = {key: [value, 0.0] for key, value in casualties_to_allocate.items()}
        casualties_to_allocate = self.sort_casualties_by_potential_survival(casualties_to_allocate)
        if self.next_casualty(casualties_to_allocate,skill ,arrival_time,max_capacity) is not None:
            return True
        else:
            return False

    def get_max_required(self):
        max_required = {}
        for skill in self.max_required:
            max_required[skill] = int(self.max_required[skill])
        return max_required


