import copy
import functools
from functools import reduce

from Simulator.SimulationComponents import *
import enum




class MedicalUnit(ServiceProvider):
    """
    Class that represent a medical unit. medical unit can provide one of the skills_activities:
    treatment, upload, transportation for urgent, medium, and non-urgent casualties
    """

    def __init__(self, _id,  speed, skills, skill_and_triage_tuple, unit_type, max_capacity, triage_score,
                 time_born=0.0, location=[0.0, 0.0]):
        """
        initial medical unit
        :param _id: The entity id
        :param time_born: the time that the entity was born
        :param location: the entity location
        :param speed: the medical unit speed drive
        :param skills: list of skill that the medical unit can provide.
        :rtype [(activity, triage)]
        :param unit_type: the medical unit type (ALS, BLS, Motorcycle)
        :rtype MedicalUnitType
        :param max_capacity: ({triage:max_mun},maximum score of capacity each skill has score)
        param triage_score: {triage:score_per_activity}
        :rtype int

        """
        ServiceProvider.__init__(self, _id=_id, time_born=time_born, location=location, speed=speed, skills=skills)

        self.skills_and_triage_tuple = skill_and_triage_tuple
        self._max_capacity = max_capacity
        self.current_capacity = self._max_capacity[1]
        self.unit_type = unit_type
        self.is_full = False  # is_full: is the medical unit full
        self.uploaded_casualties = []  # the casualties that currently on to the medical unit
        self._triage_score = triage_score
        self.workload = dict.fromkeys(self.skills_and_triage_tuple)
        self.load_capacity()
        self.near_hospital =[0.0, 0.0]  # updated later


    def load_capacity(self):
        """
        After arriving to a hospital the medical unit is refilled
        the capacity is determined by MedicalUnitType object

        """
        self.current_capacity = self._max_capacity[1]
        self.workload = {k: self._max_capacity[0][k[1]] for k in self.workload}

    def load_casualty(self, casualty):
        """
        Add casualty to loaded casualties
        :param casualty:
        :return: none
        """
        self.uploaded_casualties.append(casualty)

    def arrived_to_hospital(self, hospital: Entity):
        """
        when medical unit arrives to a hospital it initiates the loaded casualties and refill
        :return:
        """
        self.load_capacity()
        self.uploaded_casualties.clear()
        self.update_location(hospital.location)

    def update_status(self, status: Status):
        self.status = status

    def update_time(self, time: float):
        self.update_last_time(time)

    def get_max_capacity(self):
        return copy.deepcopy(self._max_capacity)

    def get_capacity(self):
        return (copy.deepcopy(self._max_capacity[0]), self.current_capacity)

    def accept_offers(self, offers_received, allocation_version=0):

        from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = {key[0]: value for key, value in self.workload.items()}
        allocate = True
        capacity = copy.copy(self._max_capacity[1])

        # NCLO
        NCLO = 0
        NCLO_offer_counter = 0
        current_xi = {}
        response_offers = []
        all_providable_skills = self.get_sr_skill_location(offers_received)



        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)

            # accepting the offer as is (or arriving earlier)
            if allocate and offer.arrival_time >= next_available_arrival_time + travel_time and \
                    capacity > 0 and offer.amount is not 0:
                current_xi[len(current_xi)] = VariableAssignment(original_object=offer)
                # NCLO
                NCLO_offer_counter += 1

                next_available_arrival_time += travel_time
                leave_time = copy.copy(offer.leaving_time)

                offer.arrival_time = round(next_available_arrival_time, 2)
                offer.leaving_time = None
                offer.duration = None
                offer.mission = []
                amount_requested = offer.amount
                offer.amount = next_available_skills[offer.skill]
                next_available_skills[offer.skill] -= amount_requested
                next_available_arrival_time = leave_time
                next_available_location = copy.deepcopy(offer.location)
                capacity -= offer.max_capacity
                offer.max_capacity = (copy.deepcopy(self._max_capacity[0]), copy.copy(offer.max_capacity) + capacity)
            # cannot allocate as is - send best offer
            else:
                # if capacity <=0:
                #     # got go hospital and refill
                #     travel_time_to_hospital = round(self.travel_time(next_available_location, self.near_hospital), 2)
                #     next_available_location = copy.copy(self.near_hospital)
                #     travel_time = travel_time_to_hospital
                #     next_available_skills = {key[0]: value for key, value in self.workload.items()}
                #     capacity = copy.copy(self._max_capacity[1])

                offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
                offer.amount = next_available_skills[offer.skill]
                offer.max_capacity = (copy.deepcopy(self._max_capacity[0]), copy.copy(capacity))
                offer.leaving_time = None
                offer.mission = []
                allocate = False
            if offer not in response_offers:
                response_offers.append(offer)

        # # got go hospital and refill
        # travel_time_to_hospital = round(self.travel_time(next_available_location, self.near_hospital), 2)
        # next_available_location = copy.copy(self.near_hospital)
        # travel_time = travel_time_to_hospital
        # next_available_skills = {key[0]: value for key, value in self.workload.items()}
        # capacity = copy.copy(self._max_capacity[1])
        #
        # # send next available time and skills after refill:
        # for requester, skill, location in all_providable_skills:
        #     travel_time = round(self.travel_time(next_available_location, location), 2)
        #     arrival_time = round(next_available_arrival_time + travel_time,2)
        #     offer = VariableAssignment(provider=self._id, requester=requester,skill=skill,
        #                        amount=next_available_skills[skill],arrival_time=arrival_time,
        #                                max_capacity=(copy.copy(self._max_capacity[0]), capacity),location=location )
        #     if offer not in response_offers:
        #         response_offers.append(offer)

        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers

    def accept_incremental_offer(self, offers_received, current_xi):

        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = {key[0]: value for key, value in self.workload.items()}
        capacity = copy.copy(self._max_capacity[1])


        # NCLO
        NCLO = 0
        NCLO_offer_counter = 0
        response_offers = []

        if len(offers_received) <= 0:
            return NCLO, current_xi, response_offers


        for offer in current_xi.values():
            response_offers.append(copy.deepcopy(offer))

        # accept first offer
        offer = offers_received[0]
        if offer.utility > 0:
            offer.accept_offer()
            current_xi[len(current_xi)] = copy.deepcopy(offer)
            response_offers.append(offer)
            offers_received.remove(offer)
            # for next offers
            next_available_arrival_time = offer.leaving_time
            next_available_location = copy.deepcopy(offer.location)
            next_available_skills = {key[0]: value for key, value in self.workload.items()}
            for o in current_xi.values():
                next_available_skills[o.skill] -= o.amount
            complete_capacity = reduce(lambda x, key: x + current_xi[key].max_capacity, current_xi, 0)
            capacity = copy.copy(self._max_capacity[1] - complete_capacity)

        NCLO_offer_counter += 1
        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)
            NCLO_offer_counter += 1
            offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
            offer.leaving_time = None
            offer.duration = None
            offer.mission = []
            offer.amount = next_available_skills[offer.skill]
            offer.max_capacity = (copy.deepcopy(self._max_capacity[0]), copy.copy(capacity))
            # cannot allocate as is - send best offer
            response_offers.append(offer)

        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers

    def accept_full_schedule_offer(self, offers_received):
        from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = {key[0]: value for key, value in self.workload.items()}
        capacity = copy.copy(self._max_capacity[1])

        # NCLO
        NCLO = 0
        NCLO_offer_counter = 0
        current_xi = {}
        response_offers = []

        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)

            # accepting the offer as is (or arriving earlier)
            if offer.arrival_time >= next_available_arrival_time + travel_time and \
                    capacity > 0 and offer.amount is not 0:
                current_xi[len(current_xi)] = VariableAssignment(original_object=offer) # todo - deepcopy
                # NCLO
                NCLO_offer_counter += 1

                next_available_arrival_time += travel_time
                leave_time = copy.copy(offer.leaving_time)

                offer.arrival_time = round(next_available_arrival_time, 2)
                offer.leaving_time = None
                offer.duration = None
                offer.mission = []
                amount_requested = offer.amount
                offer.amount = next_available_skills[offer.skill]
                next_available_skills[offer.skill] -= amount_requested
                next_available_arrival_time = leave_time
                next_available_location = copy.deepcopy(offer.location)
                capacity -= offer.max_capacity
                offer.max_capacity = (copy.deepcopy(self._max_capacity[0]), capacity+copy.copy(offer.max_capacity))
            # cannot allocate as is - send best offer
            else:
                travel_time = round(self.travel_time(next_available_location, offer.location), 2)
                capacity_requested = offer.max_capacity
                offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
                if offer.amount == 0: offer.amount = next_available_skills[offer.skill]
                offer.amount = min(next_available_skills[offer.skill], offer.amount)
                offer.max_capacity = (copy.deepcopy(self._max_capacity[0]),
                                      capacity)
                offer.leaving_time = None
                if len(offer.mission) > 0 and capacity > 0:
                    offer.mission = [offer.mission[i] for i in range(0,min(next_available_skills[offer.skill], len(offer.mission)))]
                    next_available_arrival_time =offer.arrival_time + functools.reduce\
                        (lambda acc, x: acc+ x['duration'], offer.mission, 0)
                    offer.leaving_time = next_available_arrival_time
                    # update times & location & capacity
                    next_available_skills[offer.skill] -= len(offer.mission)

                    next_available_location = copy.deepcopy(offer.location)

                    from Simulator.CTTD.CttdSimulatorComponents import get_skill_capacity_points
                    capacity_to_reduce = functools.reduce(lambda acc, x: acc + get_skill_capacity_points(
                       x['mission'].get_triage_by_time(0.0)), offer.mission, 0)
                    capacity -= capacity_to_reduce
                    current_xi[len(current_xi)] = copy.deepcopy(offer)
                    offer.mission = []

            if offer not in response_offers:
                response_offers.append(offer)


        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers


    def get_sr_skill_location(self, offers_received):
        list_of_all = [[offer.requester, offer.skill, offer.location]
        for offer in offers_received if offer.amount > 0]
        new_list = []
        for requester,skill,location in list_of_all:
            if new_list.__contains__([requester,skill,location]):
                continue
            else:
                new_list.append([requester,skill,location])
        return new_list

    def arrive_to_requester(self, last_time, location):
        self.status = Status.ON_MISSION

        self.update_location(location)

        self.last_time_updated= last_time


    def update_capacity(self, service, current_time):
        amount_received = max(self._max_capacity[0].values())
        for mission_dict in service.mission:
            if mission_dict['leaving_time'] <= current_time:
                from Simulator.CTTD.CttdSimulatorComponents import get_skill_capacity_points
                capacity_to_reduce =  get_skill_capacity_points( mission_dict['mission'].get_triage_by_time(0.0))
                self.current_capacity -= capacity_to_reduce
                self.last_time_updated = mission_dict['leaving_time']
                service.last_workload_use = self.last_time_updated
                amount_received -= 1
                self.uploaded_casualties.append(mission_dict['mission'])
        return self.last_time_updated, amount_received

    def __deepcopy__(self, memodict={}):
        copy_m_unit = MedicalUnit(self._id,  self.speed, self.skills, self.skills_and_triage_tuple,
                                          self.unit_type, self._max_capacity, self._triage_score, self.last_time_updated,
                                          self.location)

        return copy_m_unit

