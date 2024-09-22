import random
from Simulator.AbstractSimulator import AbstractServiceRequester, AbstractServiceProvider
from Simulator.AbstractSimulator.AbstractServiceRequester import Requester
from Simulator.AbstractSimulator.AbstractServiceProvider import Provider
from Simulator.SimulationComponents import Skill, Simulation

# problem variables

location_min_x = 1
location_max_x = 50
location_min_y = 1
location_max_y = 50
travel_speed = 50  # km per hour
euclidian_distance_threshold = 50  # who can be my neighbor - within euc distance
num_skill_types = 4
max_skill_ability_needed = 3  # how much of the skill does the requester need
max_skill_ability_provided = 2 # how much of the skill does the provider have
max_capacity_per_skill = 4# max for cap function 2
cap_multiplier = 0.5
max_cap_penalty = 0
min_utility = 750
max_utility = 2000
min_utility_threshold = 0  # less than this number = not worth the effort
max_requester_duration = 0  # [hours] time fluctuation (from min needed to min needed + max_time_per_requester)
mean_time_per_skill = 0.5  # time it takes to complete one skill unit

# skills_activities params
skill_params = {"num_skill_types": num_skill_types,
                                "max_skill_ability_provided": max_skill_ability_provided,
                                "max_skill_ability_needed": max_skill_ability_needed,
                                "max_capacity_per_skill": max_capacity_per_skill,
                                "cap_multiplier": cap_multiplier,
                                "max_cap_penalty": max_cap_penalty,
                                "mean_time_per_skill": mean_time_per_skill}

# utility params
utility_params = {"min_utility": min_utility, "max_utility": max_utility,
                  "min_utility_threshold": min_utility_threshold}


location_params = {"location_min_x": location_min_x, "location_max_x": location_max_x,
                   "location_min_y": location_min_y, "location_max_y": location_max_y,
                                   "euclidian_distance_threshold": euclidian_distance_threshold}


class AbstractSimulatorCreator(Simulation):
    def __init__(self, number_of_providers, number_of_requesters, prob_id):
        Simulation.__init__(self, number_of_providers, number_of_requesters, prob_id)

        self.min_utility_threshold = utility_params["min_utility_threshold"]
        self.location_params = location_params
        self.utility_params = utility_params

        # unpack skill info
        self.num_skill_types = skill_params["num_skill_types"]
        self.max_skill_ability_needed = skill_params["max_skill_ability_needed"]
        self.max_skill_ability_provided = skill_params["max_skill_ability_provided"]
        self.max_capacity_per_skill = skill_params["max_capacity_per_skill"]
        self.max_cap_penalty = skill_params["max_cap_penalty"]
        self.cap_multiplier = skill_params["cap_multiplier"]
        self.mean_time_per_skill = skill_params["mean_time_per_skill"]

        # generate entities

        self.max_requester_duration = max_requester_duration
        self.travel_speed = travel_speed
        self.create_requesters()
        self.create_providers()
        self.available_skills = []
        self.create_all_the_problem_skills()

        # create locations for all agents
        super().create_initial_locations(self.providers, location_params)
        super().create_initial_locations(self.requesters, location_params)

    # creates all requesters
    def create_requesters(self):
        for i in range(self.number_of_providers, self.number_of_providers + self.number_of_requesters):
            # randon needed skills_activities and workload
            skills_needed = self.create_skills_dict_for_entity(self.max_skill_ability_needed)
            # random max cap for skill {Skill: int}
            max_required = self.get_required_per_skill(skills_chosen=skills_needed)
            # random duration for skill from normal distribution
            time_per_skill = self.create_time_per_skill(skills_chosen=skills_needed)
            # random max util for each skill
            max_util = self.create_max_util(skills_needed)
            # max_time for requester
            max_time = self.create_max_time(time_per_skill)
            requester = self.create_single_requester(id_=i, skills_needed=skills_needed, max_required=max_required,
                                                     time_per_skill=time_per_skill, max_util=max_util,
                                                     max_time=max_time)

            self.requesters.append(requester)

    # creates all providers
    def create_providers(self):
        for i in range(self.number_of_providers):
            skill_set = self.create_skills_dict_for_entity(self.max_skill_ability_provided)
            provider = self.create_single_provider(id_=i, skill_set=skill_set)
            self.providers.append(provider)

    @staticmethod
    def create_single_requester(id_, skills_needed, max_required, time_per_skill, max_util, max_time):
        return Requester(_id=id_, skills_needed=skills_needed, max_required=max_required,
                         time_per_skill_unit=time_per_skill, max_util=max_util, max_time=max_time,
                         utility_threshold_for_acceptance=min_utility_threshold)

    @staticmethod
    def create_single_provider(id_, skill_set):
        return Provider(_id=id_, skill_set=skill_set,
                        travel_speed=travel_speed, utility_threshold_for_acceptance=min_utility_threshold)

    def create_all_the_problem_skills(self):
        for s in range(0, self.num_skill_types):
            self.available_skills.append(Skill(skill_id=s))

    def create_skills_dict_for_entity(self, max_skill_ability):
        # rand number of skill types to be chosen
        num_skills_to_choose = self.random_num.randint(1, self.num_skill_types)

        # chooses skills_activities without replacement
        skills_avail = list(range(0, self.num_skill_types))

        # rand the skills_activities type for the entity
        skills_chosen = self.random_num.sample(population=skills_avail, k=num_skills_to_choose)

        # rand number of workload for each type
        workload_avail = list(range(1, max_skill_ability + 1))
        workload_chosen = self.random_num.choices(population=workload_avail, k=num_skills_to_choose)

        # {skill: workload}
        final_skill_dict = dict(zip(skills_chosen, workload_chosen))
        return final_skill_dict

    # defines maximum cap for the cap function
    def get_required_per_skill(self, skills_chosen):
        max_required = {}
        for skill in skills_chosen.keys():
            max_optional = min(self.max_capacity_per_skill, skills_chosen[skill])
            max_required_for_skill = self.random_num.randint(1, max_optional)
            max_required[skill] = max_required_for_skill

        return max_required

    def create_time_per_skill(self, skills_chosen):
        time_per_skill_unit = {}
        for skill in skills_chosen.keys():
            time_per_skill_unit[skill] = abs(round(self.random_num.gauss(self.mean_time_per_skill, 1), 2))
            if time_per_skill_unit[skill] == 0:
                time_per_skill_unit[skill] = 0.1
        return time_per_skill_unit

    def create_max_util(self, skills_needed):
        min_util = self.utility_params["min_utility"]
        max_util = self.utility_params["max_utility"]
        util = {}
        for skill in skills_needed.keys():
            util[skill] = self.random_num.randint(min_util, max_util)
        return util

    def create_max_time(self, time_per_skill):
        all_time = 0
        for skill, time in time_per_skill.items():
            all_time += time

        max_time = round(self.random_num.uniform(all_time * 3, all_time * 3 + self.max_requester_duration), 2)

        return max_time

    def __str__(self):
        return "Problem " + str(self.prob_id) + ", With " + str(len(self.requesters)) + " Requesters and " \
               + str(len(self.providers)) + " Providers." + "\n" + "Number of Skill Types: " + \
               str(self.num_skill_types) + ", Max Ability Needed per Skill " + str(self.max_skill_ability_needed) + \
               ", Max Ability Provided per Skill " + str(self.max_skill_ability_provided) + \
               ", Max Capacity per Skill " + str(self.max_capacity_per_skill) + "\n" + \
               "Distance Threshold for Neighboring Agents: " + str(
            self.location_params["euclidian_distance_threshold"]) + "\n" + "\n" + \
               self.print_neighborhoods() + "\n" + self.print_max_capacity() + "\n" + self.print_max_abilities_needed() \
               + "\n" + self.print_max_abilities_providers() + "\n" + self.print_max_times()

    def print_max_abilities_needed(self):
        str_max = "Skill Max Abilities Needed:" + "\n"
        for requester in self.requesters:
            for skill, ability in requester.skills_needed.items():
                str_max += "Requester " + str(requester.id_) + " Skill: " + str(skill) + ", ability needed: " + \
                           str(ability) + ","
            str_max += "\n"
        return str_max

    def print_max_abilities_providers(self):
        str_1 = "Skill Max Abilities Providers Have:" + "\n"
        for provider in self.providers:
            str_1 += "Provider " + str(provider.id_) + ": "
            for skill, ability in provider.skill_set.items():
                str_1 += " Skill: " + str(skill) + ", ability available: " + \
                         str(ability) + ","
            str_1 += "\n"
        return str_1

    def print_neighborhoods(self):
        str_1 = "Neighboorhoods:" + "\n"
        for provider in self.providers:
            str_neigh = "Provider " + str(provider.id_) + " Skills: " + str(list(provider.skill_set.keys())) + \
                        ", || Neighboring: "
            for requester in provider.neighbors:
                str_neigh += "Requester " + str(requester) + " Skills: " + \
                             str(list(self.get_agent(requester).skills_needed.keys())) + ", "
            str_1 += str_neigh + "\n"
        return str_1

    def print_max_capacity(self):
        str_max = "Skill Max Capacities:" + "\n"
        for requester in self.requesters:
            for skill in requester.skills_needed.keys():
                str_max += "Requester " + str(requester.id_) + " Skill: " + str(skill) + ", providers needed: " + \
                           str(requester.max_required[skill]) + ","
            str_max += "\n"
        return str_max

    def print_max_times(self):
        str_max = "Requester Finishing Times:" + "\n"
        for requester in self.requesters:
            str_max += "Requester " + str(requester.id_) + " Finishes at: " + str(requester.max_time)
            str_max += "\n"
        return str_max







