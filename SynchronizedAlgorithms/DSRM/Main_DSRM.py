import enum
import copy

from SynchronizedAlgorithms.DSRM.DSRM_agents import DsrmSP, DsrmSR
from SynchronizedAlgorithms.SynchronizedSolver import SynchronizedSolverSOMAOP, VariableAssignment



sim_debug = True
algorithm_outcome_debug = False

# events classes----------------------------------------------------------------

class EventType(enum.Enum):
    INIT_SIMULATION = 0
    END_SIMULATION = 1
    PROVIDER_LEAVES_REQUESTER = 2
    PROVIDER_ARRIVES_TO_REQUESTER = 3


class Event(object):
    def __init__(self, arrival_time, type_):
        self.arrival_time = arrival_time
        self.type_ = type_

    def __str__(self):
        return str(self.type_) + " " + str(self.arrival_time)


class EndSimulationEvent(Event):
    def __init__(self, arrival_time):
        super().__init__(arrival_time, EventType.END_SIMULATION)
        self.importance = -1

    def __str__(self):
        return "End Simulation"


class InitializeSimulationEvent(Event):
    def __init__(self, arrival_time):
        super().__init__(arrival_time, EventType.INIT_SIMULATION)
        self.importance = 2
    def __str__(self):
        return "Initialize simulation"


class ProviderArriveToRequesterEvent(Event):
    def __init__(self, arrival_time, provider, requester, skill, mission):
        super().__init__(arrival_time, EventType.PROVIDER_ARRIVES_TO_REQUESTER)
        self.provider = provider
        self.requester = requester
        self.skill = skill
        self.mission = mission
        self.importance = 1

    def __str__(self):
        return "Provider Arrive event at: %s P: %s R: %s s: %s m: %s" % \
            (self.arrival_time, self.provider, self.requester, self.skill, self.mission)


class ProviderLeaveRequesterEvent(Event):
    def __init__(self,arrival_time, provider, requester, skill, mission):
        super().__init__(arrival_time, EventType.PROVIDER_LEAVES_REQUESTER)
        self.provider = provider
        self.requester = requester
        self.skill = skill
        self.mission = mission
        self.importance = 0

    def __str__(self):
        return "Provider Leave event at %s P: %s R: %s S: %s M: %s" \
            %(self.arrival_time, self.provider, self.requester, self.skill, self.mission)




#----------------------------------------------------------------

class DSRM(SynchronizedSolverSOMAOP):
    def __init__(self, problem_id, providers, requesters, termination=2000, bid_type=0,
                 mailer=None, algorithm_version=0,  simulator_on=True):
        # version & bid
        self.bid_type = bid_type
        self.version = algorithm_version
        self.simulator_on = simulator_on
        self.SPs = self.create_SPs(providers)
        self.SRs = self.create_SRs(requesters)
        SynchronizedSolverSOMAOP.__init__(self, problem_id=problem_id,
                                          providers=copy.deepcopy(self.SPs), requesters=copy.deepcopy(self.SRs),
                                          mailer=mailer, termination=termination)

        # simulation variables
        self.last_time = 0
        self.current_time = 0
        self.next_event = None
        self.event_diary = []
        self.event_diary.append(InitializeSimulationEvent(0))

    def execute_algorithm(self):
        self.record_data()
        if sim_debug:
            self.print_remaining_resources()
        while self.event_diary:
            self.event_diary = sorted(self.event_diary, key=lambda event: (event.arrival_time, event.importance))


            self.next_event = self.event_diary.pop(0)
            if sim_debug:
                print("------------------", self.next_event, "------------------")
            self.last_time = self.current_time
            self.current_time = self.next_event.arrival_time
            self.mailer.current_time = self.current_time

            if isinstance(self.next_event, InitializeSimulationEvent):
                self.run_gale_shapley()
                continue

            elif isinstance(self.next_event, ProviderArriveToRequesterEvent):
                self.handle_provider_arrives_to_requester_event()
                continue

            elif isinstance(self.next_event, ProviderLeaveRequesterEvent):
                self.handle_provider_leaves_requester_event()
                # in the event that there are multiple leaving events at the same time - all leave before running alg
                if not (self.event_diary and isinstance(self.event_diary[0], ProviderLeaveRequesterEvent) \
                        and self.event_diary[0].arrival_time == self.current_time):
                   self.record_data()
                   self.run_gale_shapley()
                continue

        self.handle_simulation_end_event()
        if sim_debug:
            self.print_remaining_resources()


#this is a check
    #start iteration of the
    def run_gale_shapley(self):
        self.update_all_agent_parameters()  # update skills and locations
        self.remove_irrelevant_agents_for_algorithm()  # remove srs by end time and skills needed, sps by skills left
        initial_requesters = copy.copy(self.SRs)
        self.reset_agents_for_DSRM()  # reset sp chosen, sr accepted and cap

        # both types of agents left
        while self.still_has_algorithm_agents():
            self.remove_unaccepted_offers()
            iteration = -1

            self.reset_requesters_for_GS()  # reset requester neighbors

            while not self.is_terminated() or iteration == -1:  # GS algorithm single run
                # agents react to the messages they received in the last iteration and send new msgs
                self.providers_react_to_msgs(iteration)
                # agents receive messages from current iteration
                self.agents_receive_msgs()

                self.requesters_react_to_msgs(iteration)
                self.agents_receive_msgs()

                iteration += 1

            self.update_requester_neighbors()

            self.update_algorithm_agents()

        self.retrieve_events(initial_requesters)

    def update_all_agent_parameters(self):
        for provider in self.all_providers:
            provider.update_location(self.current_time)
            provider.update_skill_usage(self.current_time)

        for requester in self.all_requesters:
            requester.update_skills_received(self.current_time)
            requester.reset_amount_of_working()
            requester.update_time_per_skill_unit(self.current_time) # TODO needed??
            requester.reset_offers_received_by_skill()

    def remove_irrelevant_agents_for_algorithm(self):
        self.SRs = copy.copy(self.all_requesters)
        self.SPs = copy.copy(self.all_providers)
        relevant_requesters = []
        for provider in self.all_providers:
            relevant_requesters += [sr for sr in provider.neighbors if self.get_agent_by_id(sr).max_time > provider.last_update_time]

        for requester in self.all_requesters:
            # not relevant time-wise anymore
            if requester.getId() not in relevant_requesters:   #all_round_nehibor_skill
                self.SRs.remove(requester)
                self.remove_requester_neighbors(requester._id)
                continue

            # if the requester has at least one skill he needs, keep him
            for skill_needed, ability_needed in requester.sim_temp_temp_skills_needed.items():
                if ability_needed > 0:
                    break
                # otherwise remove him
                else:
                    self.SRs.remove(requester)
                    self.remove_requester_neighbors(requester._id)

        for provider in self.all_providers:
            for skill, ability in provider.skill_set.items():
                if ability > 0:
                    break
            else:
                self.SPs.remove(provider)
                self.remove_provider_neighbors(provider._id)
                continue

        # for requester in self.all_requesters:
        #     for provider in self.all_providers:
        #         for skill in provider.skill_set:
        #             if requester.temp_simulation_entity.is_provider_needed(provider.temp_simulation_entity.get_max_capacity(), provider.t_now, skill):
        #                 break
        #             elif requester.getId() in provider.neighbors:
        #                 provider.neighbors.remove(requester.getId())
        #                 if len(provider.neighbors) == 0:
        #                     self.SPs.remove(provider)


    def remove_requester_neighbors(self, sr_removed):
        for sp in self.SPs:
            if sr_removed in sp.neighbors:
                sp.neighbors.remove(sr_removed)

    def remove_provider_neighbors(self, sp_removed):
        for sr in self.SRs:
            if sp_removed in sr.neighbors:
                sr.neighbors.remove(sp_removed)

    def reset_agents_for_DSRM(self):
        for agent in self.all_requesters + self.all_providers:
            agent.reset_for_DSRM()


    def still_has_algorithm_agents(self):
        return len(self.SRs) > 0 and len(self.SPs) > 0

    def reset_requesters_for_GS(self):
        for agent in self.SRs:
            agent.reset_for_GS()

    # checks if all agents have terminated
    def is_terminated(self):
        for requester in self.SRs:
            if not requester.check_termination():
                return False
        return True  # only if they all terminated

    def providers_react_to_msgs(self, iteration):
        for provider in self.SPs: #self.all_providers:
            if iteration == -1:
                provider.initialize()
            else:
                provider.compute()

    def requesters_react_to_msgs(self, iteration):
        for requester in self.SRs: #self.all_requesters:
            if iteration == -1:
                requester.initialize()  # initialize
            else:
                requester.compute()

    def update_requester_neighbors(self):

        # remove skills that have reached cap
        for sr in self.SRs:
            neighbors_by_skill_temp = copy.deepcopy(sr.neighbors_by_skill)
            for skill in sr.neighbors_by_skill.keys():
                if len(sr.GS_accepted_providers[skill]) >= sr.sim_temp_max_required[skill]:
                    del neighbors_by_skill_temp[skill]
            sr.neighbors_by_skill = neighbors_by_skill_temp


        # remove neighbors that have been matched
        for sr in self.SRs:
            to_keep = []
            for sp in sr.neighbors:
                sp_agent = self.get_agent_by_id(sp)
                if sp_agent.chosen_requester is None:
                    to_keep.append(sp)
            sr.neighbors = copy.deepcopy(to_keep)

        # remove neighbors that have been matched from remaining skills
        for sr in self.SRs:
            for skill in sr.neighbors_by_skill:
                sr.neighbors_by_skill[skill] = [sp for sp in sr.neighbors_by_skill[skill] if sp in sr.neighbors]

        # remove neighbors that cant give any skill
        for sr in self.SRs:
            to_remove = []
            for sp in sr.neighbors:
                for skill in sr.skills_needed:
                    if skill in sr.util_j.keys():
                        if sp in sr.util_j[skill].keys():
                            if sr.util_j[skill][sp] <= sr.simulation_entity.utility_threshold_for_acceptance:
                                if skill in sr.neighbors_by_skill.keys():
                                    sr.neighbors_by_skill[skill].remove(sp)
                    if skill in sr.neighbors_by_skill.keys():
                        if sp in sr.neighbors_by_skill[skill]:
                            break
                        else:
                            to_remove.append(sp)
                if sp not in [neighbor for skill in sr.neighbors_by_skill for neighbor in sr.neighbors_by_skill[skill]]:
                    to_remove.append(sp)
            sr.neighbors = [sp for sp in sr.neighbors if sp not in to_remove]



    def update_algorithm_agents(self):
        # remove providers that have been matched
        self.algorithm_providers = [sp for sp in self.SPs if sp.chosen_requester is None]

        # remove requesters that have no more neighbors
        self.algorithm_requesters = [sr for sr in self.SRs if sr.neighbors]

        # remove sps that arent anyones neighbors
        to_remove = []
        for sp in self.algorithm_providers:
            for sr in self.algorithm_requesters:
                if sp._id in sr.neighbors:
                    break
            else:
                to_remove.append(sp)
        self.SPs = [sp for sp in self.algorithm_providers if sp not in to_remove]

    def remove_unaccepted_offers(self):
        for sr in self.SRs:
            sr.remove_unaccepted_offers()

    def retrieve_events(self, initial_algorithm_requesters):
        self.event_diary = []

        for requester in initial_algorithm_requesters:
            self.event_diary.extend(requester.retrieve_GS_solution_events())

        # so that the providers receive their time schedules
        self.agents_receive_msgs()

    def handle_provider_arrives_to_requester_event(self):
        event_provider = self.get_agent_by_id(self.next_event.provider)
        event_provider.arrive_to_requester(self.current_time)

        event_requester = self.get_agent_by_id(self.next_event.requester)
        event_requester.provider_arrives_to_requester(self.next_event.provider, self.next_event.skill,
                                                      self.current_time)

    def handle_provider_leaves_requester_event(self):
        event_provider = self.get_agent_by_id(self.next_event.provider)
        event_provider.leave_requester(self.current_time)

        event_requester = self.get_agent_by_id(self.next_event.requester)
        event_requester.provider_leaves_requester(self.next_event.provider, self.next_event.skill, self.current_time)

    def handle_simulation_end_event(self):
        self.record_data()


    def calculate_global_utility(self):
        util = 0
        for sr in self.all_requesters:
            util += sr.final_utility()
            # if sim_debug:
            #     print("SR: " + str(sr.getId()))
            #     print(sr.simulation_times_for_utility)

        return util

    def create_SPs(self, simulation_providers_entities):
        SPs = [DsrmSP(simulation_entity=provider, algo_version=self.version)\
               for provider in simulation_providers_entities]
        return SPs

    def create_SRs(self, simulation_requester_entities):
        SRs = [DsrmSR(simulation_entity=requester, bid_type=self.bid_type, algo_version=self.version)
               for requester in simulation_requester_entities]
        return SRs

    def print_remaining_resources(self):
        for sp in self.all_providers:
            print("P: %s remaining skills: %s" % (sp._id, sp.skill_set))

        for sr in self.all_requesters:
            print("R: %s remaining skills: %s" % (sr._id, sr.skills_needed))