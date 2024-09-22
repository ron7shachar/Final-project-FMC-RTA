import copy
from Simulator.SimulationComponents import ServiceRequester, get_skill_amount_dict


class Requester(ServiceRequester):
    def __init__(self, _id, skills_needed, time_born=0.0, location=[0.0, 0.0], utility_type=0, penalty_for_delay=0.95,
                 max_required={}, time_per_skill_unit={}, max_util=1000, max_time=10,
                 utility_threshold_for_acceptance=50, rate_util_fall=5):
        ServiceRequester.__init__(self, _id=_id, time_born=time_born, location=location,
                                  skills=list(skills_needed.keys()), max_time=max_time)

        self.time_per_skill_unit = time_per_skill_unit  # {skill: time per unit} duration for skill unit
        self.utility_threshold_for_acceptance = utility_threshold_for_acceptance
        self.init_skill_definition(skills_needed=skills_needed, max_required=max_required, max_util=max_util)

        # utility variables
        self.penalty_for_delay = penalty_for_delay  # penalty multiplied by provider travel times
        self.rate_util_fall = rate_util_fall  # how much utility is affected by time

        self.simulation_times_for_utility = {}  # {time: amount working before}
        self.reset_simulation_times_for_utility()  # from maya's simulator - for the finite calculation

        self.util_j = {}  # {skill:{provider:utility}} from maya's simulator

    # 1 - calculates final utility according to team_simulation_times_for_utility dict
    def calc_utility_by_schedule(self, simulation_times=None):
        """

        :param simulation_times: {Skill:{time: amount working before}}
        :return: utility for times
        """
        if simulation_times is None:
            simulation_times = self.simulation_times_for_utility

        all_util = 0
        for skill, amount_needed in self.skills_requirements.items():
            if skill in simulation_times.keys():
                rate_of_util_fall = ((- self.max_util[skill] / self.rate_util_fall) / self.max_time)
                util_available = self.max_util[skill]
                util_received = 0
                last_time = 0
                total_amount_complete = 0
                for time, amount_working in simulation_times[skill].items():
                    time_elapsed = time - last_time
                    skills_complete = min(amount_needed - total_amount_complete,
                                          time_elapsed / self.time_per_skill_unit[skill])

                    if amount_working == 0:  # no service given in this time frame - util is lost
                        util_available += rate_of_util_fall * time_elapsed
                    else:  # service is given in this time frame - util is not lost
                        total_amount_complete += skills_complete
                        cap_multiplier = cap(amount_working, self.max_required[skill])
                        util = util_available * (skills_complete / amount_needed) * cap_multiplier
                        util_received += util
                        if total_amount_complete >= amount_needed:
                            break
                    last_time = time

                    if time > self.max_time:
                        break

                all_util += util_received
            # print("req",self.id_, "skill ", skill, "utility ", util_received)

        if all_util < 0:
            return 0

        return round(all_util, 2)

    # initiates team_simulation_times_for_utility dict
    def reset_simulation_times_for_utility(self):
        for skill in self.skills:
            self.simulation_times_for_utility[skill] = {}

    def allocated_offers(self, skills_needed_temp, offers_received_by_skill, allocation_version=0):
        NCLO = 0
        allocated_offers = {}

        if allocation_version == 3:
            offers_received_by_skill, skills_needed_temp= self.remove_accepted_offers\
                (offers_received_by_skill, skills_needed_temp)

        for skill in skills_needed_temp:
            allocated_offers[skill] = set()
            if skill not in offers_received_by_skill.keys():
                print("Skill not in offers_received_by_skill")
            skill_offers_by_arrival = [offer for offer in offers_received_by_skill[skill] if
                                       offer.utility is not 0]
            skill_offers_by_arrival = list(sorted(skill_offers_by_arrival, key=lambda offer: offer.arrival_time))
            q = min(self.max_required[skill], len(skill_offers_by_arrival))
            # NCLO
            NCLO += super().number_of_comparisons(q, len(skill_offers_by_arrival)) # todo - neighbors not skills
            offers_to_allocate = copy.copy(skill_offers_by_arrival[:q])
            unallocated_offers = copy.copy(skill_offers_by_arrival[q:])
            update_unallocated(unallocated_offers)  # skill_offers_by_arrival[q:]
            # {offer: (arrival time, workload)}
            offers_skill_available_dict = get_skill_amount_dict(offers_to_allocate)
            for offer in offers_skill_available_dict.keys(): offer.mission = []

            while skills_needed_temp[skill] > 0 and offers_skill_available_dict:
                # order offers by next skill unit work start
                offers_skill_available_dict = dict(sorted(offers_skill_available_dict.items(),
                                                          key=lambda offer: offer[0].leaving_time))
                # NCLO
                NCLO += super().number_of_comparisons(1, len(offers_skill_available_dict))

                offer_stats = next(iter(offers_skill_available_dict.items()))
                allocated_offers[skill].add(offer_stats[0])
                # arrival time
                offer_stats[0].leaving_time = round(offer_stats[0].leaving_time + self.time_per_skill_unit[skill], 2)
                offer_stats[0].duration = round(offer_stats[0].leaving_time - offer_stats[0].arrival_time, 2)
                # skill left
                offer_stats[0].amount += 1
                offer_stats[1][0] -= 1
                skills_needed_temp[skill] -= 1
                offer_stats[0].mission.append(1)

                # no skill left
                if offer_stats[1][0] == 0:
                    del offers_skill_available_dict[offer_stats[0]]
        return allocated_offers, NCLO

    def remove_accepted_offers(self, offers_received_by_skill, skills_needed_temp):
        for skill, offers in offers_received_by_skill.items():
            for offer in offers:
                if offer.accept:
                    skills_needed_temp[skill] -= offer.amount
            offers[:] = [offer for offer in offers if not offer.accept]
        return offers_received_by_skill, skills_needed_temp

    def is_offer_relevant_according_to_accepted_offers(self,offer, offers_accepted):
        return True
    def calc_converge_bid_to_offer(self, skill, offer):
        rate_of_util_fall = ((- self.max_util[skill] / self.rate_util_fall) / self.max_time)
        util_available = self.max_util[skill] + rate_of_util_fall * offer.arrival_time
        util_received = util_available * (offer.amount / self.skills_requirements[skill])
        return max(round(util_received, 2), 0)

    def calc_simple_bid(self, offer):
        skill = offer.skill
        amount_neighbor_skill = offer.amount
        if skill in self.skills_requirements:
            skill_amount_needed = self.skills_requirements[skill]
            if amount_neighbor_skill > skill_amount_needed:
                amount_neighbor_skill = copy.deepcopy(skill_amount_needed)

            rate_of_util_fall = ((- self.max_util[skill] / self.rate_util_fall) / self.max_time)
            util_available = self.max_util[skill]- rate_of_util_fall * offer.travel_time
            best_util_received = util_available * offer.amount/ skill_amount_needed
            return round(best_util_received, 2)
        return 0

    def calc_truncated_bids(self, offers,util_j, accepted_providers, neighrors):
        NCLO = 0
        #sort offers by time arrival
        # loop on all offers skills
        for skill in offers.keys():
            if skill not in accepted_providers.keys():
                accepted_providers[skill] = set()
            # max required is the minimum between max needed and offers sent
            max_required = min(len(offers[skill]),self.max_required[skill])
            # sort offers by time arrival
            offers_by_arrival = list(sorted(offers[skill], key=lambda offer: offer.arrival_time))
            # neighbors_considered = how many have we tried to include
            neighbors_considered = []

            # dont need to give utility to agents other than the max needed
            if len(accepted_providers[skill]) >= max_required:
                continue

            for offer in offers_by_arrival:
                neighbor_id = offer.provider
                # can do at least one unit or is already giving me service
                # if offer.arrival_time + self.time_per_skill_unit[skill] <= self.max_time:
                neighbors_considered.append(neighbor_id)
                util = self.get_util(neighbors_considered + list(accepted_providers[skill]), skill, offers_by_arrival)
                self.update_specific_utilities(neighbors_considered, skill, util, accepted_providers[skill], util_j)
                # NCLO
                NCLO += super().number_of_comparisons(len(neighbors_considered), len(neighrors))
                # will stop if we have all cap and also completed skill or we ran out of neighbors
                all_considerd = list(set(neighbors_considered).union(accepted_providers[skill]))
                if len(all_considerd) >= max_required:
                    break
        return NCLO

    def get_util(self, neighbors_working_together, skill,offers):
        util = self.max_util[skill]
        total_skill = 0
        total_travel_times = 0
        for provider_id in neighbors_working_together:
            offer = next(filter(lambda offer: offer.provider == provider_id, offers), None)
            total_skill += offer.amount
            total_travel_times += offer.travel_time

        if total_skill > self.skills_requirements[skill]:
            total_skill = copy.deepcopy(self.skills_requirements[skill])



        # penalty for delay * distance = utility lost for arrival
        util -= self.penalty_for_delay * total_travel_times
        # rate_of_util_fall = ((- self.max_util[skill] / self.rate_util_fall) / self.max_time)
        # util += rate_of_util_fall * total_travel_times

        # skill cover factor
        if total_skill / self.skills_requirements[skill] < 1:
            util *= total_skill / self.skills_requirements[skill]

        # cap function
        util *= cap(len(neighbors_working_together), self.max_required[skill])

        return round(util, 2)

    def update_specific_utilities(self, neighbors_considered, skill, util, accepted_providers, util_j):
        number_sharing = len(neighbors_considered) + len(accepted_providers)

        for neighbor in neighbors_considered:
            if neighbor not in util_j[skill]:
                util_j[skill][neighbor] = 0

            if util_j[skill][neighbor] < round(util / number_sharing, 2):
                util_j[skill][neighbor] = round(util / number_sharing, 2)
            else:
                util -= util_j[skill][neighbor]
                number_sharing -= 1

    def final_utility(self, allocated_offers=None, SP_view=None, cost=None, simulation_times=None):
        if simulation_times is None:
            simulation_times = self.create_simulation_times(allocated_offers, SP_view)
        else:
            simulation_times = {k: dict(sorted(v.items())) for k, v in simulation_times.items()}

        all_util = 0
        for skill, amount_needed in self.skills_requirements.items():
            if skill in simulation_times.keys():
                rate_of_util_fall = ((- self.max_util[skill] / self.rate_util_fall) / self.max_time)
                util_available = self.max_util[skill]
                util_received = 0
                last_time = 0
                total_amount_complete = 0
                for time, amount_working in simulation_times[skill].items():
                    time_elapsed = time - last_time
                    skills_complete = round(min(amount_needed - total_amount_complete,
                                                (time_elapsed / self.time_per_skill_unit[skill]) * amount_working),2)

                    if amount_working == 0:  # no service given in this time frame - util is lost
                        util_available += rate_of_util_fall * time_elapsed
                    else:  # service is given in this time frame - util is not lost
                        total_amount_complete += skills_complete
                        cap_multiplier = cap(amount_working, self.max_required[skill])
                        util = util_available * (skills_complete / amount_needed) * cap_multiplier
                        util_received += util
                        if total_amount_complete >= amount_needed:
                            break
                    last_time = time

                    if time > self.max_time:
                        break

                all_util += util_received
                # print("req",self._id, "skill ", skill, "utility ", util_received)

        if all_util < 0:
            return 0

        return round(all_util, 2)

    # for calculating final utility - makes a dict of the outcome of the times
    def create_simulation_times(self, allocated_offers, SP_view):
        simulation_times = {}
        if SP_view is None:
            schedules = allocated_offers
        else:
            schedules = super().create_schedules_by_skill_by_SP_view(SP_view)

        for skill in schedules:
            schedules[skill] = sorted(schedules[skill], key=lambda item: item.arrival_time)
            simulation_times[skill] = {}
            leaving_times = []
            amount_working = 0

            for schedule in schedules[skill]:
                leaving_times.append(schedule.leaving_time)
                leaving_times = sorted(leaving_times)
                # next can arrive
                if schedule.arrival_time < leaving_times[0]:
                    if schedule.arrival_time not in simulation_times[skill]:
                        simulation_times[skill][schedule.arrival_time] = amount_working
                    amount_working += 1
                # someone needs to leave before next can arrive
                else:
                    # everyone that must leave leaves
                    while schedule.arrival_time >= leaving_times[0]:
                        next_leaving = leaving_times.pop(0)
                        if next_leaving not in simulation_times[skill]:
                            simulation_times[skill][next_leaving] = amount_working
                        amount_working -= 1

                    if schedule.arrival_time not in simulation_times[skill].keys():
                        simulation_times[skill][schedule.arrival_time] = amount_working
                    amount_working += 1

            # whoever hasnt left leaves
            while leaving_times:
                next_leaving = leaving_times.pop(0)
                if next_leaving not in simulation_times[skill]:
                    simulation_times[skill][next_leaving] = amount_working
                amount_working -= 1

        return simulation_times


    def update_cap(self, skill, workload):
        pass

    def reduce_skill_requirement(self, service, current_time):
        skills_received = int(round(current_time - service.last_workload_use, 2) /
                              self.time_per_skill_unit[service.skill])
        service.last_workload_use += self.time_per_skill_unit[service.skill] * skills_received
        service.last_workload_use = round(service.last_workload_use, 2)
        self.skills_requirements[service.skill] -= skills_received
        return skills_received

    def is_offer_relevant(self, offer):
        if offer.skill in self. skills:
            return True
        else:
            return False
    def get_care_time(self, skill,time):
        return self.time_per_skill_unit[skill]

    def get_max_required(self):
        return self.max_required
def update_unallocated(offers):
    for offer in offers:
        offer.utility = 0
        offer.amount = 0






# 2 - cap function, defining the efficiency of a team at the SR
def cap(team, max_required):
    # linear
    if team == 0:
        return 0

    if team >= max_required:
        return 1
    if max_required == 1:
        return 1
    rate = 0.5/(max_required - 1)
    cap_outcome = 0.5 + rate * (team - 1)

    return cap_outcome



