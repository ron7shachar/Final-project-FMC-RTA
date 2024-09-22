from Solver.SOMAOP.BasicSOMAOP import *

from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
import enum

dbug = False
bid_debug = False
offers_debug = False
class ProviderStatus(enum.Enum):
    at_requester = 1
    in_transport = 2

class DsrmSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, algo_version=0):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=algo_version)

        # all rounds GS variables
        self.chosen_requester = None

        # single round GS variables
        self.play_round = True
        self.offers_received = []

        #  simulation variables
        self.status = ProviderStatus.in_transport
        self.last_update_time = 0
        self.current_service = None
        self.temp_simulation_entity = copy.deepcopy(simulation_entity)
    # --------------------GS ALGORITHM PRE-PROCESSING RELATED METHODS--------------------------
    def reset_for_DSRM(self):
        self.chosen_requester = None

    def initialize(self):
        # so that the SP doesn't take part in the GS when it has already chosen before this round
        if self.chosen_requester is not None:
            self.play_round = False
        else:
            self.play_round = True

        if self.play_round:
            self.util_i = {}
            self.send_service_proposal_msg()

    def compute(self):
        if self.play_round:
            if self.offers_received:
                best_choice = self.compute_GS_response()
                self.send_GS_responses(best_choice)
                self.chosen_requester = copy.deepcopy(best_choice)
                self.offers_received = []

    def send_GS_responses(self, best_choice):
        for sr in self.neighbors:
            msg = GSResponseMsg(self._id, sr, copy.deepcopy(best_choice))
            self.mailer.send_msg(msg)



    def compute_GS_response(self):
        utilities_for_options = {}
        if self.chosen_requester is not None:
            utilities_for_options[self.chosen_requester] = self.util_i[self.chosen_requester[0]][
                self.chosen_requester[1]]

        for offer_received in self.offers_received:
            utilities_for_options[offer_received] = self.util_i[offer_received[0]][offer_received[1]]

        # NCLO
        self.NCLO += Agent.number_of_comparisons(1, len(utilities_for_options))

        max_offer = max(utilities_for_options, key=utilities_for_options.get)
        return max_offer  # requester, skill tuple that provider wants to be sent to

    def send_service_proposal_msg(self):
        for requester in self.neighbors:

            skills = copy.deepcopy(self.skill_set)
            for skill in skills.keys():
                if requester in self.neighbors_by_skill[skill]:
                    offer = VariableAssignment(self.getId(), requester, skill,
                                                copy.deepcopy(self.neighbor_locations[requester]))
                    if isinstance(self.simulation_entity, MedicalUnit):
                        offer.max_capacity = copy.deepcopy(self.temp_simulation_entity.get_capacity())

                    travel_time = round(self.travel_time(self.location, self.neighbor_locations[requester]), 2)
                    offer.arrival_time = round(travel_time + self.last_update_time, 2)
                    offer.amount = self.skill_set[skill]
                    offer.location = self.neighbor_locations[requester]
                    offer.travel_time = round(travel_time)
                    offer.last_workload_use = offer.arrival_time
                    msg_value = ServiceProposalMsg(sender_id=self._id, receiver_id=requester,
                                            context=offer)
                    self.mailer.send_msg(msg_value)


    # --------------------SIMULATION RELATED METHODS--------------------------
    def arrive_to_requester(self, current_time):
        self.status = ProviderStatus.at_requester

        self.update_location(current_time)

        self.last_update_time = current_time

        self.temp_simulation_entity.arrive_to_requester(current_time, self.location)

    def leave_requester(self, current_time):
        self.status = ProviderStatus.in_transport

        # also updates last update time
        self.update_skill_usage(current_time)

        self.current_service = None

    def update_skill_usage(self, current_time):

        if self.current_service is not None and self.current_service.arrival_time < current_time: # provider has already arrived
            self.last_update_time, self.skill_set[self.current_service.skill] = self.temp_simulation_entity.update_capacity(self.current_service, current_time)
            if self.skill_set[self.current_service.skill] == 0:
                del self.skill_set[self.current_service.skill]

            # todo - if  reduce capacity need to be None?
            self.current_service = None

            # if self.skill_set[self.current_service.skill] == 0:
            #     del self.skill_set[self.current_service.skill]
            #     # todo - if finished current service need to be None?
            #     self.current_service = None

    def update_location(self, current_time):


        if self.current_service is not None:
            arrival_location = self.current_service.location

            if self.status == ProviderStatus.at_requester:
                self.location = arrival_location

            elif self.status == ProviderStatus.in_transport:
                if self.location[0] == self.current_service.location[0] and \
                        self.location[1] == self.current_service.location[1]:
                    return

                time_travel_begin = self.find_leaving_time()

                if time_travel_begin == current_time:  # just left
                    return

                ratio = find_ratio_of_travel_complete(time_travel_begin=time_travel_begin,
                                                      arrival_time=self.current_service.arrival_time,
                                                      current_time=current_time)
                x_dist_ratio = abs((arrival_location[0] - self.location[0])) * ratio
                y_dist_ratio = abs((arrival_location[1] - self.location[1])) * ratio

                current_location = []

                if self.location[0] < arrival_location[0]:
                    current_location.append(round(self.location[0] + x_dist_ratio, 2))
                else:
                    current_location.append(round(self.location[0] - x_dist_ratio, 2))

                if self.location[1] < arrival_location[1]:
                    current_location.append(round(self.location[1] + y_dist_ratio, 2))
                else:
                    current_location.append(round(self.location[1] - y_dist_ratio, 2))

                self.location = current_location

    def find_leaving_time(self):
        arrival_location = self.current_service.location
        arrival_time = self.current_service.arrival_time

        x_dist_total = abs((arrival_location[0] - self.location[0]))
        y_dist_total = abs((arrival_location[1] - self.location[1]))

        horizontal_dist_total = (x_dist_total ** 2 + y_dist_total ** 2) ** 0.5

        time_travel_begin = round(arrival_time - (horizontal_dist_total / self.simulation_entity.speed), 2)

        return time_travel_begin

    def agent_receive_a_single_msg(self, msg):
        if isinstance(msg, BidMessage):
            self.util_i[msg.sender] = msg.information

        elif isinstance(msg, OfferMessage):
            for skill_offer in msg.information:
                self.offers_received.append((msg.sender, skill_offer))

        elif isinstance(msg, UpdateServiceMessage):
            if self.current_service is not None and msg.sender == self.current_service.requester and \
                    msg.information is None:
                self.current_service = None

            if msg.information is not None:
                if self.current_service is None or self.current_service.requester != msg.sender:
                    self.status = ProviderStatus.in_transport

                self.current_service = copy.deepcopy(msg.information)
    def send_msgs(self):
        pass

class DsrmSR(SR):
    def __init__(self,simulation_entity: ServiceRequester, bid_type, t_now=None, algo_version=0):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=bid_type, t_now=t_now,
                        algorithm_version=algo_version)

        self.allocated_offers = {}
        self.offers_to_send = []
        self.current_utility = 0
        self.time_per_skill_unit = {}
        self.temp_simulation_entity = copy.deepcopy(simulation_entity)
        self.finished_offers = {}


        # ---- multiple round GS variables
        self.GS_accepted_providers_utility = {}
        self.all_round_neighbor_skills = {}
        # ---- single round GS variables
        # SPs that have currently approved my offer {skill: [sp id]}
        self.GS_accepted_providers = {}
        # SPs i sent offer to {skill: [sp id]}
        self.GS_has_offered = {}
        self.GS_has_not_offered = {}
        # responses received from SPs {sp id: (chosen sr id, skill)}
        self.GS_SP_choices = {}
        # skills that have terminated {skill: t\f}


        # ---- simulation variables
        self.sim_temp_temp_skills_needed = copy.deepcopy(self.skills_needed)
        self.sim_temp_max_required = copy.deepcopy(self.simulation_entity.get_max_required())

        self.current_services = []  # [variable assignments]
        self.working_by_skill = {}
        self.amount_working = {}  # {skill:amount}
        self.neighbors_skill = {} # {neighbor id: {skill:workload}}
   # --------------------GS ALGORITHM PRE-PROCESSING RELATED METHODS--------------------------
    def reset_for_DSRM(self):
        self.reset_GS_accepted_providers()
        self.reset_GS_accepted_providers_utility()
        self.reset_offers_received_by_skill()
        self.all_round_neighbor_skills = {}

    def reset_GS_accepted_providers(self):
        self.GS_accepted_providers = {}
        for skill in self.neighbors_by_skill:
            self.GS_accepted_providers[skill] = set()

    def reset_GS_accepted_providers_utility(self):
        self.GS_accepted_providers_utility = {}
        for skill in self.skills_needed:
            self.GS_accepted_providers_utility[skill] = {}

    # --------------------GS ALGORITHM RELATED METHODS--------------------------
    def reset_for_GS(self):
        self.neighbors = []

    def update_neighbors_by_skill(self):
        self.neighbors_by_skill = {}
        for neighbor in self.neighbors:
            for skill in self.neighbors_skill[neighbor]:
                if skill not in self.neighbors_by_skill:
                    self.neighbors_by_skill[skill] = [neighbor]
                else:
                    self.neighbors_by_skill[skill].append(neighbor)

    def update_terminated(self):
        self.terminated = {}
        # skills that will play this round of GS
        for skill in self.neighbors_by_skill:
            self.terminated[skill] = False

    def initialize_GS_has_not_offered(self):
        self.GS_has_not_offered = {}
        for skill in self.neighbors_by_skill:
            self.GS_has_not_offered[skill] = [sp for sp in self.neighbors_by_skill[skill]
                                              if (sp in self.util_j[skill]
                                                  and self.util_j[skill][sp] > self.simulation_entity.utility_threshold_for_acceptance)]

    # initiates util_j dict
    def reset_util_j(self):
        self.util_j = {}
        for skill in self.neighbors_by_skill.keys():
            self.util_j[skill] = {}

    def reset_GS_has_offered(self):
        self.GS_has_offered = {}
        for skill in self.neighbors_by_skill:
            self.GS_has_offered[skill] = []
            self.GS_has_not_offered[skill] = []


    def update_cap(self):
        for skill in self.sim_temp_temp_skills_needed:
            workload = 0
            max_require = copy.copy(self.sim_temp_max_required[skill])
            can_provide_service = 0
            # if skill in self.GS_accepted_providers.keys():
            #     for offer in self.offers_received_by_skill[skill]:
            #         if offer.provider in self.GS_accepted_providers[skill]:
            #             max_require -= offer.amount
            #         else:
            #             can_provide_service += offer.amount
            if skill in self.neighbors_by_skill and \
                len(self.neighbors_by_skill[skill]) < self.sim_temp_max_required[skill]:
                workload = len(self.neighbors_by_skill[skill])
                self.sim_temp_max_required[skill] = workload

            else:
                workload = self.sim_temp_max_required[skill]
            self.temp_simulation_entity.update_cap(skill, workload)

    def update_time_per_skill_unit(self, time):
        for skill in self.sim_temp_temp_skills_needed:
           self.time_per_skill_unit[skill] = self.temp_simulation_entity.get_care_time(skill, time)

    def initialize(self):
        self.update_neighbors_by_skill()
        self.update_relevant_offers()
        self.update_cap()  # update cap to be the minimum between number of neighbors & max cap
        self.reset_GS_has_offered()

        self.GS_SP_choices = {}
        self.reset_util_j()
        self.update_terminated()
        self.calculate_utilities()
        if offers_debug:
            print("SR: %s" % str(self._id))
            for skill in self.offers_received_by_skill.keys():
                for offer in self.offers_received_by_skill[skill]:
                    print("SP: %s A.T: %s S: %s amount: %s" %(offer.provider,offer.arrival_time, skill, offer.amount))
        if bid_debug:
            print("SR: %s util_j: %s" % (str(self._id), self.util_j))
        self.send_utilities()

        self.initialize_GS_has_not_offered()  # all SPs that sent an offer
        self.make_and_send_GS_offers()  # send for each sp the best skill offer

    # 2 - algorithm compute (single agent response to iteration)
    def compute(self):
        self.update_GS_needs()  # update temporary approvals
        if not self.check_termination():
            self.make_and_send_GS_offers()
        self.GS_SP_choices = {}

    def update_GS_needs(self):
        for sp, choice in self.GS_SP_choices.items():
            choice_sr = choice[0]
            choice_skill = choice[1]
            if choice_sr == self._id:
                for skill in self.GS_accepted_providers:
                    if skill != choice_skill and sp in self.GS_accepted_providers[skill]:
                        self.GS_accepted_providers[skill].remove(sp)
                        del self.GS_accepted_providers_utility[skill][sp]
                self.GS_accepted_providers[choice_skill].add(sp)
                self.GS_accepted_providers_utility[choice_skill][sp] = self.util_j[choice_skill][sp]
            else:
                for skill in self.GS_accepted_providers:
                    if sp in self.GS_accepted_providers[skill]:
                        self.GS_accepted_providers[skill].remove(sp)
                        del self.GS_accepted_providers_utility[skill][sp]


        self.GS_has_not_offered = {}
        for skill in self.neighbors_by_skill:
            self.GS_has_not_offered[skill] = [sp for sp in self.neighbors_by_skill[skill]
                                              if (sp not in self.GS_has_offered[skill] and sp in self.util_j[skill]
                                                  and self.util_j[skill][sp] > self.simulation_entity.utility_threshold_for_acceptance)]

            if (len(self.GS_has_not_offered[skill]) == 0 or
                    (len(self.GS_accepted_providers[skill]) >= self.sim_temp_max_required[skill])):
                self.terminated[skill] = True
            else:
                self.terminated[skill] = False

    def send_utilities(self):
        for neighbor in self.neighbors:
            neighbor_utils = {}
            for skill in self.util_j:
                if neighbor in self.util_j[skill] and self.util_j[skill][neighbor] > self.simulation_entity.utility_threshold_for_acceptance:
                    neighbor_utils[skill] = self.util_j[skill][neighbor]
            msg = BidMessage(self._id, neighbor, copy.deepcopy(neighbor_utils))
            self.mailer.send_msg(msg)

    def send_offer_msgs(self, offers_by_neighbor):
        for neighbor in offers_by_neighbor:
            msg = OfferMessage(self._id, neighbor, offers_by_neighbor[neighbor])
            self.mailer.send_msg(msg)

    def remove_unaccepted_offers(self):
        for skill in self.offers_received_by_skill:
            to_keep = copy.deepcopy(self.offers_received_by_skill[skill])
            for offer in self.offers_received_by_skill[skill]:
                if offer.provider not in self.GS_accepted_providers[skill]:
                    to_keep.remove(offer)
            self.offers_received_by_skill[skill] = to_keep

    # 4 - receive incoming information from neighbors
    def agent_receive_a_single_msg(self, msg):
        if isinstance(msg, ServiceProposalMsg):
            if msg.information.skill in self.skills_needed:

                for skill in self.skills_needed:
                    if msg.information.arrival_time+ self.time_per_skill_unit[skill] < self.max_time:
                        if msg.information not in self.offers_received_by_skill[msg.information.skill]:
                            self.offers_received_by_skill[msg.information.skill].append(msg.information)
                        if msg.sender not in self.neighbors: self.neighbors.append(msg.sender)
                        if  msg.sender in self.neighbors_skill.keys() and \
                        msg.information.skill not in self.neighbors_skill[msg.sender]:
                            self.neighbors_skill[msg.sender].append(msg.information.skill)
                        else:
                            self.neighbors_skill[msg.sender] = []
                            self.neighbors_skill[msg.sender].append(msg.information.skill)
                        break

            if msg.sender in self.all_round_neighbor_skills.keys():
                self.all_round_neighbor_skills[msg.sender].append(msg.information.skill)
            else:
                self.all_round_neighbor_skills[msg.sender] = []
                self.all_round_neighbor_skills[msg.sender].append(msg.information.skill)

        elif isinstance(msg, BidMessage):
            self.GS_SP_choices[msg.sender] = msg.information

        elif isinstance(msg, GSResponseMsg):
            self.GS_SP_choices[msg.sender] = msg.information

    def make_and_send_GS_offers(self):
        offers_by_neighbor = {}
        for skill in self.neighbors_by_skill:
            best_to_offer_skill = self.choose_best_SPs_to_offer(skill)
            for neighbor in best_to_offer_skill:
                if neighbor in offers_by_neighbor:
                    offers_by_neighbor[neighbor].append(skill)
                else:
                    offers_by_neighbor[neighbor] = [skill]

                self.GS_has_offered[skill].append(neighbor)

        self.send_offer_msgs(offers_by_neighbor)

    def choose_best_SPs_to_offer(self, skill):

        if skill not in self.GS_accepted_providers.keys():
            self.GS_accepted_providers[skill] = set()
        number_to_allocate = self.sim_temp_max_required[skill] - len(self.GS_accepted_providers[skill])

        if skill not in self.util_j:
            self.util_j[skill] = {}
        utilities_for_options = copy.deepcopy(self.util_j[skill])
        to_remove = [sp for sp in utilities_for_options if sp not in self.GS_has_not_offered[skill]]
        for sp in to_remove:
            del utilities_for_options[sp]

        best_SPs_to_offer = []

        # self.print_options(utilities_for_options, skill)


        while number_to_allocate > 0 and len(utilities_for_options) > 0:
        #     # NCLO
            self.NCLO += Agent.number_of_comparisons(1, len(utilities_for_options))

            max_offer = max(utilities_for_options, key=utilities_for_options.get)
            best_SPs_to_offer.append(max_offer)
            # remove agent from the temp dict
            del utilities_for_options[max_offer]

            number_to_allocate = number_to_allocate - 1

        return best_SPs_to_offer

    def print_options(self, utilities_for_options, skill):
        utilities_for_options = sorted(utilities_for_options.items(), key=lambda item: item[1], reverse=True)
        print(self.id_, "for skill", skill, "choosing top", self.sim_temp_max_required[skill], "from:")
        for option in utilities_for_options:
            print("SP", option[0], "Util", option[1])

    def calculate_utilities(self):
        if self.bid_type == 3:
            self.update_simple_bids()
        elif self.bid_type == 1:
            self.update_truncated_bids()

    def update_simple_bids(self):
        """
        update self.util_j
        :return:
        """
        for skill in self.skills_needed:
            for offer in self.offers_received_by_skill[skill]:
                if skill in self.neighbors_by_skill:
                    self.util_j[offer.skill][offer.provider] = self.simulation_entity.calc_simple_bid(copy.deepcopy(offer))
                    if self.util_j[offer.skill][offer.provider] == 0:
                        del self.util_j[offer.skill][offer.provider]
                        self.neighbors_by_skill[offer.skill].remove(offer.provider)
                # self.NCLO += super().number_of_comparisons(1, 1) # len(self.offers_received_by_skill[skill])
    def update_truncated_bids(self):
        """
        update self.util_j
        :return: none
        """
        self.NCLO += self.simulation_entity.calc_truncated_bids(copy.deepcopy(self.offers_received_by_skill), self.util_j, self.GS_accepted_providers, self.neighbors)

        for skill, util_j in self.util_j.items():
            if len(util_j) > self.sim_temp_max_required[skill]:
                new_util_j = dict(sorted(util_j.items(), key=lambda item: item[1], reverse=True)[:self.sim_temp_max_required[skill]])
                self.util_j[skill] = new_util_j

        # skill_needed = copy.deepcopy(self.skills_needed)
        # skill_needed ={key:value for key,value in skill_needed.items() if key in self.neighbors_by_skill.keys()}
        # # todo add new def to simulation entity - get the offers. util j and update the util_j in DS
        # offers_to_allocate = copy.deepcopy(self.offers_received_by_skill)
        # allocated_offers, self.NCLO = self.temp_simulation_entity.allocated_offers(skill_needed, offers_to_allocate)
        # for skill in allocated_offers:
        #     for offer in allocated_offers[skill]:
        #         offer_to_sent = {skill:[offer]}
        #         self.util_j[offer.skill][offer.provider] = self.temp_simulation_entity.final_utility(offer_to_sent, cost = False)
        #         if self.util_j[offer.skill][offer.provider] == 0:
        #             del self.util_j[offer.skill][offer.provider]
        #             if offer.provider in self.neighbors_by_skill[offer.skill]:
        #                 self.neighbors_by_skill[offer.skill].remove(offer.provider)


    def send_msgs(self):
        pass

    def final_utility(self):
        simulation_times_for_utility = {}
        for skill in self.finished_offers:
            simulation_times_for_utility[skill] = {}
            arrival_times = [offer.arrival_time for offer in self.finished_offers[skill]]
            leaving_times = [offer.leaving_time for offer in self.finished_offers[skill]]
            all_times = list(sorted(set(arrival_times + leaving_times),key=lambda time: time))
            amount_of_working = 0
            for time in all_times:
                simulation_times_for_utility[skill][time] = amount_of_working
                if time in arrival_times:
                    amount_of_working += 1
                if time in leaving_times:
                    amount_of_working -= 1

        return self.simulation_entity.final_utility(simulation_times=simulation_times_for_utility, allocated_offers=self.finished_offers)

        # return self.simulation_entity.final_utility(simulation_times=self.simulation_times_for_utility, allocated_offers=self.finished_offers)



    # todo - this is the new one
    # def get_util(self, neighbors_working_together, skill):
    #     util = self.max_util[skill]
    #     total_skill = 0
    #
    #     for provider_id in neighbors_working_together:
    #         total_skill += self.neighbor_skills[provider_id][skill]
    #
    #     if total_skill > self.sim_temp_temp_skills_needed[skill]:
    #         total_skill = copy.deepcopy(self.sim_temp_temp_skills_needed[skill])
    #
    #     # skill cover factor
    #     if total_skill / self.sim_temp_temp_skills_needed[skill] < 1:
    #         util *= total_skill / self.sim_temp_temp_skills_needed[skill]
    #
    #     # cap function
    #     util *= cap(len(neighbors_working_together), self.sim_temp_max_required[skill])
    #
    #     return util

    def update_specific_utilities(self, neighbors_considered, skill, util):
        number_sharing = len(neighbors_considered) + len(self.GS_accepted_providers[skill])

        for neighbor in neighbors_considered:
            if neighbor not in self.util_j[skill]:
                self.util_j[skill][neighbor] = 0

            if self.util_j[skill][neighbor] < round(util / number_sharing, 2):
                self.util_j[skill][neighbor] = round(util / number_sharing, 2)
            else:
                util -= self.util_j[skill][neighbor]
                number_sharing -= 1

    # todo - this is the new one
    # def update_specific_utilities(self, neighbors_considered, skill, util):
    #     number_sharing = len(neighbors_considered) + len(self.GS_accepted_providers[skill])
    #
    #     for neighbor in self.GS_accepted_providers[skill]:
    #         if self.GS_accepted_providers_utility[skill][neighbor] >= round(util / number_sharing, 2):
    #             util -= self.GS_accepted_providers_utility[skill][neighbor]
    #             number_sharing -= 1
    #             continue
    #
    #     for neighbor in neighbors_considered:
    #         travel_time = self.neighbor_arrival_times[neighbor]
    #         util = round(util / number_sharing - travel_time * self.penalty_for_delay, 2)
    #
    #         if util <= 0:
    #             self.util_j[skill][neighbor] = 0
    #         else:
    #             self.util_j[skill][neighbor] = util

    def check_termination(self):
        for skill, termination in self.terminated.items():
            if not termination:
                return False
        return True

    # --------------------GS ALGORITHM POST-PROCESSING RELATED METHODS--------------------------
    def retrieve_GS_solution_events(self):
        from SynchronizedAlgorithms.DSRM.Main_DSRM import ProviderLeaveRequesterEvent, ProviderArriveToRequesterEvent

        new_services = self.retrieve_services()
        previous_services = self.current_services
        self.current_services = []

        current_time = self.mailer.current_time
        events = []
        # sp needs to leave
        for service in previous_services:
            if not self.is_in_new_service(service, new_services):
                if service.arrival_time < current_time:
                    # leaving_event = ProviderLeaveRequesterEvent(arrival_time=current_time,
                    #                                             provider=service.provider, requester=self._id,
                    #                                             skill=service.skill, mission=service.mission)

                    leaving_event = ProviderLeaveRequesterEvent(arrival_time=service.last_workload_use,
                                                                provider=service.provider, requester=self._id,
                                                                skill=service.skill, mission=service.mission)
                    events.append(leaving_event)

            for skill in self.GS_accepted_providers:
                if service.provider in self.GS_accepted_providers[skill]:
                    break
            else:
                msg = UpdateServiceMessage(sender_id=self._id, receiver_id=service.provider, context=None)
                self.mailer.send_msg(msg)

        for service in new_services:
            is_continuing_service = [s for s in previous_services if s == service]
            if service.last_workload_use is None or service.last_workload_use == 0.0:
                service.last_workload_use = service.arrival_time

            if is_continuing_service and is_continuing_service[0].arrival_time < current_time:
                provider_arrival_time = is_continuing_service[0].arrival_time
                provider_added_work_time = service.duration
                provider_leave_time = round(is_continuing_service[0].last_workload_use + provider_added_work_time, 2)
                provider_amount = int(round((provider_leave_time - provider_arrival_time)
                                            / self.time_per_skill_unit[service.skill], 2))
                # service.amount = provider_amount
                service.amount = len(service.mission)
                service.arrival_time = provider_arrival_time
                service.leaving_time = provider_leave_time
                service.duration = round(service.leaving_time - service.arrival_time, 2)
                service.last_workload_use = is_continuing_service[0].last_workload_use

                # TODO: new addition:
                arrival_event = ProviderArriveToRequesterEvent(arrival_time=service.arrival_time,
                                                               provider=service.provider, requester=self._id,
                                                               skill=service.skill, mission=service.mission)
                events.append(arrival_event)
                #--------------------------------------------------------

                leaving_event = ProviderLeaveRequesterEvent(arrival_time=service.leaving_time,
                                                            provider=service.provider, requester=self._id,
                                                            skill=service.skill, mission=service.mission)
                events.append(leaving_event)

            else:
                arrival_event = ProviderArriveToRequesterEvent(arrival_time=service.arrival_time,
                                                               provider=service.provider, requester=self._id,
                                                               skill=service.skill, mission=service.mission)
                events.append(arrival_event)

                leaving_event = ProviderLeaveRequesterEvent(arrival_time=service.leaving_time,
                                                            provider=service.provider, requester=self._id,
                                                            skill=service.skill,mission=service.mission)
                events.append(leaving_event)

            msg = UpdateServiceMessage(sender_id=self._id, receiver_id=service.provider, context=service)
            self.mailer.send_msg(msg)

            self.current_services.append(service)

        return events

    # def retrieve_services(self):
    #     temp_skills_needed_temp = copy.deepcopy(self.sim_temp_temp_skills_needed)
    #     all_services = []
    #
    #     for skill in self.GS_accepted_providers:
    #         service_skill_available_dict = {}
    #         services = []
    #         for sp in self.GS_accepted_providers[skill]:
    #
    #             if skill in self.working_by_skill and sp in self.working_by_skill[skill]:
    #                 already_serving = [s for s in self.current_services if s.provider == sp and s.skill == skill]
    #                 arrival_time = already_serving[0].last_workload_use
    #             else:
    #                 arrival_time = round(self.neighbor_arrival_times[sp] + self.mailer.current_time, 2)
    #
    #             service = DSRM_Variable_Assignment(sp, self.id_, skill, self.current_location,
    #                                                amount=1, duration=self.time_per_skill_unit[skill],
    #                                                arrival_time=arrival_time,
    #                                                leaving_time=round(arrival_time + self.time_per_skill_unit[skill],
    #                                                                   2),
    #                                                last_workload_use=arrival_time)
    #             services.append(service)
    #             if self.all_round_neighbor_skills[sp][skill] > 1:
    #                 service_skill_available_dict[service] = [self.all_round_neighbor_skills[sp][skill] - 1]
    #
    #             temp_skills_needed_temp[skill] -= 1
    #
    #         while temp_skills_needed_temp[skill] > 0 and service_skill_available_dict:
    #             import math
    #             even_load = math.floor(temp_skills_needed_temp[skill] / (len(service_skill_available_dict)))
    #             extra = None
    #
    #             if even_load == 0:
    #                 extra = temp_skills_needed_temp[skill]
    #
    #             to_remove = []
    #             for offer_stats, skill_left in service_skill_available_dict.items():
    #                 min_ability = min(skill_left[0], even_load)
    #                 if even_load == 0 and skill_left[0] > 0 and extra > 0:
    #                     min_ability = 1
    #                     extra -= 1
    #                 offer_stats.amount += min_ability
    #                 offer_stats.leaving_time += self.time_per_skill_unit[skill] * min_ability
    #                 offer_stats.leaving_time = round(offer_stats.leaving_time, 2)
    #                 offer_stats.duration += round(self.time_per_skill_unit[skill] * min_ability, 2)
    #                 skill_left[0] -= min_ability
    #                 temp_skills_needed_temp[skill] -= min_ability
    #
    #                 # no skill left
    #                 if skill_left[0] == 0:
    #                     to_remove.append(offer_stats)
    #
    #             for key in to_remove:
    #                 del service_skill_available_dict[key]
    #
    #         all_services.extend(services)
    #
    #     return all_services


    def retrieve_services(self):
        temp_skills_needed_temp = copy.deepcopy(self.sim_temp_temp_skills_needed)
        all_services = []
        accepted_offers = {}
        for skill in self.GS_accepted_providers:
            accepted_offers[skill] = [offer for offer in self.offers_received_by_skill[skill] if offer.provider in \
            self.GS_accepted_providers[skill]]
        temp_skills_needed_temp = {skill: workload for skill, workload in temp_skills_needed_temp.items() if skill in accepted_offers.keys()}
        offers, addNCLO = self.temp_simulation_entity.allocated_offers(temp_skills_needed_temp,accepted_offers)
        offers = split_offers(offers)
        self.NCLO += addNCLO
        offers_list = [value for sublist in offers.values() for value in sublist if len(value.mission) > 0]
        if dbug:
            for offer in offers_list:
                print(offer)


        return offers_list

    # --------------------SIMULATION RELATED METHODS--------------------------
    def provider_arrives_to_requester(self, provider_id, skill, current_time):

        if skill not in self.amount_working:
            self.amount_working[skill] = 0

        if skill not in self.working_by_skill:
            self.working_by_skill[skill] = []

        self.working_by_skill[skill].append(provider_id)
        self.update_amount_working(skill, current_time)
        if current_time not in self.simulation_times_for_utility[skill]:
            self.simulation_times_for_utility[skill][current_time] = self.amount_working[skill]
        self.amount_working[skill] += 1

    def update_amount_working(self, skill, current_time):
        if skill in self.finished_offers:
            for offer in self.finished_offers[skill]:
                if offer.arrival_time < current_time and offer.leaving_time >= current_time:
                    self.amount_working[skill] += 1


    def provider_leaves_requester(self, provider_id, skill, current_time):
        self.update_skills_received(current_time)

        self.current_services = [service for service in self.current_services
                                 if not (service.skill == skill and service.provider == provider_id)]

        self.working_by_skill[skill].remove(provider_id)
        self.update_amount_working(skill, current_time)

        if current_time not in self.simulation_times_for_utility[skill]:
            self.simulation_times_for_utility[skill][current_time] = self.amount_working[skill]
        self.amount_working[skill] = 0

    def update_skills_received(self, current_time):

        for service in self.current_services:
            if service.arrival_time <= current_time and service.last_workload_use <= current_time:  # provider has already arrived
                skills_received = self.temp_simulation_entity.reduce_skill_requirement(service, current_time)
                if skills_received > 0:
                    self.update_finished_offers(copy.deepcopy(service), skills_received)
                if service.skill in self.sim_temp_temp_skills_needed:
                    self.sim_temp_temp_skills_needed[service.skill] -= skills_received
                    self.skills_needed[service.skill] -= skills_received

                    if self.sim_temp_temp_skills_needed[service.skill] == 0:
                        self.remove_skill_needed(service.skill)

    def reset_amount_of_working(self):
        for skill in self.amount_working:
            self.amount_working[skill] = 0

    def update_finished_offers(self, service, skills_received):
        service.mission = service.mission[:skills_received]
        if service.skill not in self.finished_offers:
            self.finished_offers[service.skill] = []
        self.finished_offers[service.skill].append(service)
        service.leaving_time = skills_received*(service.duration/service.amount)+service.arrival_time
        service.amount = skills_received
        self.amount_working[service.skill] = 0
        self.update_amount_working(service.skill,service.leaving_time)
        if service.leaving_time not in self.simulation_times_for_utility[service.skill]:
            self.simulation_times_for_utility[service.skill][round(service.leaving_time,2)] = self.amount_working[service.skill]
        self.amount_working[service.skill] -= 1



    def remove_skill_needed(self, skill):
        del self.sim_temp_temp_skills_needed[skill]
        del self.skills_needed[skill]
        if skill in self.neighbors_by_skill.keys():
            del self.neighbors_by_skill[skill]
        for neighbor in self.neighbors_skill:
            if skill in self.neighbors_skill[neighbor]:
                self.neighbors_skill[neighbor].remove(skill)

    def update_relevant_offers(self):
        offers_accepted = {}
        for skill in self.offers_received_by_skill:
            offers_accepted[skill] = []
            for offer in self.offers_received_by_skill[skill]:
                if skill in self.GS_accepted_providers:
                    if offer.provider in self.GS_accepted_providers[skill]:
                        offers_accepted[skill].append(offer)
            for offer in self.offers_received_by_skill[skill]:
                if not self.simulation_entity.is_offer_relevant_according_to_accepted_offers(offer, offers_accepted[skill]):
                    self.offers_received_by_skill[skill].remove(offer)
                    if skill in self.neighbors_by_skill:
                        if offer.provider in self.neighbors_by_skill[skill]:
                            self.neighbors_by_skill[skill].remove(offer.provider)


    def is_in_new_service(self, service, new_services):
        for ns in new_services:
            if ns.provider == service.provider and ns.skill == service.skill:
                return True


def find_ratio_of_travel_complete(time_travel_begin, arrival_time, current_time):
    try:
        return (current_time - time_travel_begin) / (arrival_time - time_travel_begin)
    except:
        return 1

def split_offers(offers):
    return_offers = {}
    for skill in offers:
        return_offers[skill] = []
        for offer in offers[skill]:
            if len(offer.mission) > 1:
                for mission in offer.mission:
                    if isinstance(mission, dict):
                        new_offer = copy.deepcopy(offer)
                        new_offer.mission = [copy.deepcopy(mission)]
                        new_offer.arrival_time = mission['arrival_time']
                        new_offer.duration = mission['duration']
                        new_offer.leaving_time = mission['leaving_time']
                        new_offer.amount = 1
                        return_offers[skill].append(new_offer)
                        break
                    else:
                        return_offers[skill].append(offer)
                        break
            else:
                return_offers[skill].append(offer)
    return return_offers