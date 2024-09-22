import random
from abc import ABC
import copy

from Solver.SOMAOP.BasicSOMAOP import *
from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment

dbug = True



class RpaSR(SR):
    def __init__(self, simulation_entity: ServiceRequester, bid_type, t_now=None, algo_version=0):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=bid_type, t_now=t_now, algorithm_version=algo_version)

        self.allocated_offers = {}
        self.offers_to_send = []
        self.current_utility = 0


    # 1 - reset fields of algorithm


    def reset_allocated_offers(self):
        for skill in self.skills_needed:
            self.allocated_offers[skill] = set()

    # 2 - algorithm compute (single agent response to iteration)
    def compute(self):
        # self.reset_allocated_offers()

        # gives them utility 0
        self.update_unfeasible_offers_unallocated()
        self.allocate_offers()
        self.update_utilities()
        self.reset_offers_received_by_skill()

    def allocate_offers(self):
        skills_needed_temp = copy.deepcopy(self.skills_needed)

        self.allocated_offers, self.NCLO = \
            self.simulation_entity.allocated_offers(skills_needed_temp, copy.deepcopy(self.offers_received_by_skill),
                                                    allocation_version=self.algorithm_version)


    def update_utilities(self):
        for skill in self.allocated_offers:
            for offer in self.allocated_offers[skill]:
                if self.bid_type == 1:
                    offer.utility = self.simulation_entity.calc_converge_bid_to_offer(skill, offer)
                elif self.bid_type == 2:
                    skills_needed_temp = copy.deepcopy(self.skills_needed)
                    offer.utility = self.calc_shapley_value_bid(offer=offer)
                elif self.bid_type == 3:
                    offer.utility = self.calc_simple_bid(offer=offer)
                self.offers_to_send.append(offer)


    def calc_shapley_value_bid(self, offer):
        offer_receive_by_skills = copy.deepcopy(self.offers_received_by_skill)
        bid = 0
        if offer.amount == 0: return bid
        utility_all_offers = self.simulation_entity.final_utility(self.allocated_offers)
        offer_receive_by_skills_without_sp = {skill: [copy.deepcopy(o) for o in all_offers if o != offer]
                                              for skill, all_offers in offer_receive_by_skills.items()}
        offers_without_sp, _ = self.simulation_entity.allocated_offers(copy.deepcopy(self.skills_needed), offer_receive_by_skills_without_sp)
        utility_without_sp = self.simulation_entity.final_utility(offers_without_sp)
        bid = utility_all_offers - utility_without_sp
        return round(max(0, bid), 2)

#todo upcasting
    def calc_simple_bid(self, offer):
        offer_receive_by_skills = copy.deepcopy(self.offers_received_by_skill)
        bid = 0
        only_the_sp_offer = {skill: [copy.deepcopy(o) for o in all_offers if o.provider == offer.provider and o.skill == offer.skill]
                                              for skill, all_offers in offer_receive_by_skills.items()}
        only_the_sp_offer = {k:v for k,v in only_the_sp_offer.items() if v}

        skills_needed_temp = {offer.skill:self.skills_needed[offer.skill]}

        only_sp_allocated_offers, _ = self.simulation_entity.allocated_offers(skills_needed_temp,
                                                                       only_the_sp_offer)
        utility_simple = self.simulation_entity.final_utility(only_sp_allocated_offers,cost=False)
        bid = utility_simple
        return round(max(0, bid), 2)


    def update_unfeasible_offers_unallocated(self):
        unallocated = []
        for skill in self.offers_received_by_skill:
            for offer in self.offers_received_by_skill[skill]:
                if offer.arrival_time > self.max_time or offer.amount is 0:
                    unallocated.append(offer)
                    self.offers_to_send.append(offer)
        update_unallocated(unallocated)

    # 3 - after computation broadcast information to neighbors
    def send_msgs(self):
        if dbug:
            self.print_response_offers()
        while self.offers_to_send:
            offer = self.offers_to_send.pop(0)
            msg_offer = OfferMessage(self._id, offer.provider, offer)
            self.mailer.send_msg(msg_offer)

    # 4 - receive incoming information from neighbors
    def agent_receive_a_single_msg(self, msg):
        if isinstance(msg, OfferMessage):
            offer = msg.information
            self.offers_received_by_skill[offer.skill].append(offer)

    def initialize(self):
        pass

    def get_utility_by_SP_view(self, SP_view):
        allocated_offers = copy.deepcopy(self.allocated_offers)
        return self.simulation_entity.final_utility(allocated_offers, SP_view)


    def print_response_offers(self):
        print("offers from SR: " + str(self._id))
        for offer in self.offers_to_send:
            print(" %s  --> %s: %s | bid %s | A.T %s | amount %s"
                  % (offer.requester, offer.provider, offer.skill, offer.utility, offer.arrival_time, offer.amount))
            for mission in offer.mission:
                if isinstance(mission,dict):
                    print("ID: %s, Sur: %s ||" %
                          ( mission['mission'].get_id(), round(mission['mission'].survival_by_time(
                    mission['arrival_time']), 2)))



# when offer is unfeasibly - the utility is 0 and the amount needed is 0
def update_unallocated(offers):
    for offer in offers:
        offer.utility = 0
        offer.amount = 0
        offer.max_capacity = 0


class RpaSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, algo_version=0, accept_offers_version=0, alfa=0.7):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=algo_version)

        self.offers_received = []
        self.response_offers = []
        self.dumping_bids = {}  # {sr_id:{skill:}}
        self.alfa = alfa
        self.temperature = 10000

    def initialize(self):
        for offer in self.domain:
            to_offer = VariableAssignment(original_object=offer)
            travel_time = round(self.travel_time(self.location, to_offer.location), 2)
            to_offer.arrival_time = travel_time
            to_offer.amount = self.skill_set[to_offer.skill]
            self.response_offers.append(to_offer)
        # reset dumping
        self.dumping_bids = dict.fromkeys(self.neighbors, {})

    # 3 - algorithm compute (single agent response to iteration)
    def compute(self):
        self.response_offers = []
        self.accept_offers()
        self.offers_received = []

    def accept_offers(self):
        if self.algorithm_version == 0 or self.algorithm_version == 1 or self.algorithm_version == 2:
            self.current_xi = {}
            if self.algorithm_version == 0: # orderd by bid
                # sort offers by bid (inner sort by arrival time)
                self.offers_received = list(
                    sorted(self.offers_received, key=lambda offer: (offer.utility, -offer.arrival_time),
                           reverse=True))
            elif self.algorithm_version == 1:  # first offer by simulated annealing
                self.ordered_offers_by_sa()
            elif self.algorithm_version == 2:  # ordered offers by dumping
                self.update_offers_bid_by_dumping()
                self.ordered_offers_by_sa()
            self.NCLO, self.current_xi, self.response_offers = self.simulation_entity.accept_offers(
                self.offers_received)

        elif self.algorithm_version == 3:  # incremental
            self.offers_received = list(
                sorted(self.offers_received, key=lambda offer: (offer.utility, -offer.arrival_time),
                       reverse=True))
            self.NCLO, self.current_xi, self.response_offers = self.simulation_entity.accept_incremental_offer\
                (self.offers_received, self.current_xi)
        elif self.algorithm_version == 4 or self.algorithm_version == 5:
            self.offers_received = list(
                sorted(self.offers_received, key=lambda offer: (offer.utility, -offer.arrival_time),
                       reverse=True))
            self.NCLO, self.current_xi, self.response_offers = self.simulation_entity.accept_full_schedule_offer\
                (self.offers_received)


        if dbug:
            self.print_response_offers()
            self.print_current_xi()
            print('-----------------------------------------------------------------------------')
            print('\n')

    def ordered_offers_by_sa(self):
        # orders the offers by the highest bid
        self.offers_received = list(
            sorted(self.offers_received, key=lambda offer: (offer.utility, -offer.arrival_time),
                   reverse=True))
        if len(self.offers_received) == 0: return
        # select random offer
        offer_to_receive = self.random_num.choice(self.offers_received)


        # calc acceptation probability by SA
        delta_bid = self.offers_received[0].utility - offer_to_receive.utility
        if delta_bid == 0 and offer_to_receive.arrival_time!= 0:
            delta_bid = ((offer_to_receive.arrival_time - self.offers_received[0].arrival_time)/offer_to_receive.arrival_time)
        self.temperature *= 0.84
        probability = math.exp(-delta_bid / float(self.temperature))
        if self.random_num.random() < probability:
            self.offers_received.remove(offer_to_receive)
            self.offers_received.insert(0, offer_to_receive)

    def update_offers_bid_by_dumping(self):
        for offer in self.offers_received:
            if offer.skill not in self.dumping_bids[offer.requester]:
                self.dumping_bids[offer.requester][offer.skill] = offer.utility
            else:
                offer.utility = round(self.alfa * offer.utility + \
                                (1 - self.alfa) * self.dumping_bids[offer.requester][offer.skill],2)

    # 4 - after computation broadcast information to neighbors
    def send_msgs(self):
        while self.response_offers:
            offer = self.response_offers.pop(0)
            msg_availability = OfferMessage(self._id, offer.requester, offer)
            self.mailer.send_msg(msg_availability)


    # 5 - receive incoming information from neighbors
    def agent_receive_a_single_msg(self, msg):
        if isinstance(msg, OfferMessage):
            self.offers_received.append(msg.information)

    # 6 - dbug print methods
    def print_offers_received(self):
        print("print received offers:")
        for offer in self.offers_received:
            print("sp: %s, sr: %s skill: %s, bid: %s, arrival_time: %s,  munber_of_missions: %s"
             % (offer.provider, offer.requester, offer.skill, offer.utility,  offer.arrival_time, len(offer.mission)))

    def print_response_offers(self):
        print("SP: "+str(self._id))
        for offer in self.response_offers:
            print("%s --> %s: %s | T.A %s | Amount: %s"
                  % (offer.provider, offer.requester, offer.skill, offer.arrival_time, offer.amount))

    def print_current_xi(self):
        print(f"sp {self._id} current xi:")
        for offer in self.current_xi.values():
            print("%s --> %s: %s | bid: %s"
                  % (offer.provider, offer.requester, offer.skill, offer.utility))
            for mission in offer.mission:
                if isinstance(mission,dict):
                    print("\nID: %s, Sur: %s ||" %
                          (mission['mission'].get_id(), round(mission['mission'].survival_by_time(
                              mission['arrival_time']), 2)))