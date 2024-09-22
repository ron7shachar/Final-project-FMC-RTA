import copy

from Simulator.SimulationComponents import ServiceProvider, calc_distance, Status


class Provider(ServiceProvider):
    def __init__(self, _id, skill_set, utility_threshold_for_acceptance=50, travel_speed=5,
                 location=[0.0, 0.0], time_born=0):
        ServiceProvider.__init__(self, _id=_id, time_born=time_born, location=location, skills=list(skill_set.keys())
                                 , speed=travel_speed)
        # Provider Variables
        self.skill_set = skill_set  # {skill: amount}
        self.init_skill_workload(skills_set=skill_set)

        self.utility_threshold_for_acceptance = utility_threshold_for_acceptance

    def accept_offers(self, offers_received, allocation_version=0):
        """
        allocate the offers by the ordered received
        :return: NCLO, current_xi, response_offers
        """
        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = copy.deepcopy(self.workload)
        allocate = True

        # NCLO
        NCLO = 0
        NCLO_offer_counter = 0
        current_xi = {}
        response_offers = []

        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)

            # accepting the offer as is (or arriving earlier)
            if allocate and offer.arrival_time >= next_available_arrival_time + travel_time and \
                    offer.amount <= next_available_skills[offer.skill] and offer.amount is not 0:
                current_xi[len(current_xi)] = copy.deepcopy(offer)
                # NCLO
                NCLO_offer_counter += 1

                next_available_arrival_time += travel_time
                leave_time = round(next_available_arrival_time + \
                                   offer.duration, 2)

                offer.arrival_time = round(next_available_arrival_time, 2)
                offer.leaving_time = None
                offer.duration = None
                offer.missions = []
                amount_requested = offer.amount
                offer.amount = next_available_skills[offer.skill]

                next_available_skills[offer.skill] -= amount_requested
                next_available_arrival_time = leave_time
                next_available_location = copy.deepcopy(offer.location)

            # cannot allocate as is - send best offer
            else:
                offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
                offer.amount = next_available_skills[offer.skill]
                offer.leaving_time = None

            response_offers.append(offer)

        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers

    def accept_incremental_offer(self, offers_received, current_xi):
        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = copy.deepcopy(self.workload)

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
            for o in current_xi.values():
                next_available_skills[o.skill] -= o.amount

        # send new offers
        NCLO_offer_counter += 1
        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)
            NCLO_offer_counter += 1
            offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
            offer.leaving_time = None
            offer.duration = None
            offer.amount = next_available_skills[offer.skill]
            response_offers.append(offer)

        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers

    def accept_full_schedule_offer(self, offers_received):
        next_available_arrival_time = self.last_time_updated
        next_available_location = copy.deepcopy(self.location)
        next_available_skills = copy.deepcopy(self.workload)
        allocate = True

        # NCLO
        NCLO = 0
        NCLO_offer_counter = 0
        current_xi = {}
        response_offers = []

        for offer in offers_received:
            offer.utility = None
            travel_time = round(self.travel_time(next_available_location, offer.location), 2)

            # accepting the offer as is (or arriving earlier)
            if allocate and offer.arrival_time >= next_available_arrival_time + travel_time and \
                    offer.amount <= next_available_skills[offer.skill] and offer.amount is not 0:
                current_xi[len(current_xi)] = copy.deepcopy(offer)
                # NCLO
                NCLO_offer_counter += 1

                next_available_arrival_time += travel_time
                leave_time = round(next_available_arrival_time + \
                                   offer.duration, 2)

                offer.arrival_time = round(next_available_arrival_time, 2)
                offer.leaving_time = None
                offer.duration = None
                offer.missions = []
                amount_requested = offer.amount
                offer.amount = next_available_skills[offer.skill]

                next_available_skills[offer.skill] -= amount_requested
                next_available_arrival_time = leave_time
                next_available_location = copy.deepcopy(offer.location)

            # cannot allocate as is - send best offer
            else:

                amount_requested =  offer.amount
                offer.amount = min(next_available_skills[offer.skill], amount_requested)

                next_available_skills[offer.skill] -= min(next_available_skills[offer.skill], amount_requested)
                if amount_requested > 0:
                    offer.duration =round(((offer.leaving_time - offer.arrival_time)/ amount_requested)*offer.amount,2)

                next_available_location = copy.deepcopy(offer.location)
                offer.arrival_time = round(next_available_arrival_time + travel_time, 2)
                offer.leaving_time = offer.arrival_time + offer.duration
                next_available_arrival_time = offer.leaving_time
                if offer.amount>0:
                    current_xi[len(current_xi)] = copy.deepcopy(offer)
                offer.leaving_time = None


            response_offers.append(offer)

        # NCLO
        NCLO += super().number_of_comparisons(NCLO_offer_counter + 1, len(offers_received))
        return NCLO, current_xi, response_offers


    def arrive_to_requester(self, last_time, location):
        self.status = Status.ON_MISSION

        self.update_location(location)

        self.last_time_updated= last_time

    def update_capacity(self, current_service, current_time):
        skill_usage = int(current_service.amount * round(current_time - self.last_time_updated, 2) / \
                          current_service.duration)
        self.skill_set[current_service.skill] -= skill_usage

        skill_amount_left = copy.copy(self.skill_set[current_service.skill])
        if self.skill_set[current_service.skill] == 0:
            del self.skill_set[current_service.skill]

        self.last_time_updated += round((current_service.duration/current_service.amount) * skill_usage,2)
        current_service.last_workload_use = self.last_time_updated
        return  self.last_time_updated, skill_amount_left