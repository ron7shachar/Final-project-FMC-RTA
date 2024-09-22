import copy
import math
import random
from openpyxl.descriptors import Integer

from Simulator.CTTD.Casualty import Casualty
from Simulator.CTTD.DisasterSite import DisasterSite
from Simulator.CTTD.Hospital import Hospital
from Simulator.CTTD.MedicalUnit import MedicalUnit
from Simulator.SimulationComponents import Simulation
from Simulator.CTTD import RPM

location_min_x = 1
location_max_x = 80
location_min_y = 1
location_max_y = 80
location_params = {"location_min_x": location_min_x, "location_max_x": location_max_x,
                   "location_min_y": location_min_y, "location_max_y": location_max_y}

# casualties distribution
max_casualty_in_site = 10  # the max casualties in each disaster site
min_casualty_in_site = 3  # the min casualties in each disaster site
casualties_RPM_distribution = 'uniform'

# medical unit params
speed = {'ALS': 60, 'BLS': 60, 'MOTORCYCLE': 60}
medical_unit_types_and_capacities = {'ALS': {'URGENT': 2, 'MEDIUM': 4, 'NON_URGENT': 6},
                                     'BLS': {'URGENT': 0, 'MEDIUM': 2, 'NON_URGENT': 3},
                                     'MOTORCYCLE': {'URGENT': 0, 'MEDIUM': 2, 'NON_URGENT': 2}}
max_capacities = {'ALS': 180, 'BLS': 90, 'MOTORCYCLE': 90}
medical_unit_skills = {'ALS': ['treatment', 'uploading', 'transportation'],
                       'BLS':  ['treatment', 'uploading', 'transportation'],
                       'MOTORCYCLE':  ['treatment']}
medical_unit_type_probabilities = {'ALS': 0.2, 'BLS': 0.6, 'MOTORCYCLE': 0.2}

# skill & medical units  params
skills_activities = {'treatment': 1, 'uploading': 2, 'transportation': 3}
skills_weights =  {'treatment': 1, 'uploading': 0.5, 'transportation': 0.2}
triage = {'URGENT': 30, 'MEDIUM': 15, 'NON_URGENT': 10}  # {triage: score}
skills = {(key, item): value for key, value in skills_activities.items() for item in triage.keys()}

# hospital
hospital_number = 1
hospital_capacity = math.inf


# experiments params


class CttdSimulatorComponents(Simulation):

    def __init__(self, number_of_providers, number_of_requesters, prob_id):
        super().__init__(number_of_providers, number_of_requesters, prob_id)
        self.hospitals = []
        self.create_providers()
        self.create_requesters()
        self.create_hospitals()
        super().create_initial_locations(self.providers + self.requesters + self.hospitals, location_params)
        self.update_nearest_hospital_location()
    # creates all requesters
    def create_requesters(self):
        for i in range(self.number_of_providers, self.number_of_providers + self.number_of_requesters):
            number_of_casualties = self.random_num.randint(min_casualty_in_site, max_casualty_in_site)
            casualties = self.create_casualties_list(number_of_casualties, i)
            requester = self.create_single_requester(id_=i, casualties=casualties)
            self.requesters.append(requester)

    # creates all providers
    def create_providers(self):
        for i in range(self.number_of_providers):
            medical_unit_type = self.random_num.choices(list(medical_unit_type_probabilities.keys()),
                                                list(medical_unit_type_probabilities.values()))[0]
            skills_set = medical_unit_skills[medical_unit_type]
            skill_and_triage_tuple = get_skills_tuples(medical_unit_skills[medical_unit_type],
                                                       medical_unit_types_and_capacities[medical_unit_type])
            travel_speed = speed[medical_unit_type]
            triage_score = copy.deepcopy(triage)
            max_capacity = (medical_unit_types_and_capacities[medical_unit_type], max_capacities[medical_unit_type])
            provider = self.create_single_provider(id_=i, skill_set=skills_set,
                                                   skill_and_triage_tuple=skill_and_triage_tuple,
                                                   travel_speed=travel_speed, triage_score=triage_score,
                                                   max_capacity=max_capacity, mu_type=medical_unit_type)
            self.providers.append(provider)

    def create_hospitals(self):
        for i in range(0, hospital_number):
            hospital = self.create_single_hospital(id_=i)
            self.hospitals.append(hospital)


    @staticmethod
    def create_single_provider(id_, skill_set, travel_speed, triage_score, mu_type, max_capacity,skill_and_triage_tuple):
        return MedicalUnit(_id=id_, speed=travel_speed, skills=skill_set, triage_score=triage_score,
                           max_capacity=max_capacity, unit_type=mu_type, skill_and_triage_tuple=skill_and_triage_tuple)

    @staticmethod
    def create_single_requester(id_, casualties):
        return DisasterSite(id_=id_, skills=list(skills_activities.keys()),
                            casualties=copy.deepcopy(casualties), skills_weights=skills_weights)

    @staticmethod
    def create_single_hospital(id_):
        return Hospital(_id=id_, max_capacity=hospital_capacity)

    def create_casualties_list(self, number_of_casualties, disaster_site_id):
        casualties = []
        for i in range(0, number_of_casualties):
            cas_id = int(str(disaster_site_id) + str(i))
            casualty = self.create_single_casualty(cas_id, i)
            casualties.append(casualty)
        return casualties

    def create_single_casualty(self, id_, disaster_site_id):
        if casualties_RPM_distribution == 'uniform':
            cas_RPM = self.random_num.randint(0, 12)
        return Casualty(init_RPM=cas_RPM, _id=id_, disaster_site_id=disaster_site_id)

    def update_nearest_hospital_location(self):
        for agent in self.providers + self.requesters:
            nearest_hospital_location = get_nearest_entity_location(agent, self.hospitals)
            agent.near_hospital = nearest_hospital_location


def cmp_skills(activity_1, activity_2):
    if skills_activities[activity_1] < skills_activities[activity_2]:
        return -1
    elif skills_activities[activity_1] > skills_activities[activity_2]:
        return 1
    else:
        return 0


def get_skill_capacity_points(current_triage):
    return triage[current_triage]


def initial_capacity_by_type(medical_unit_type):
    """
    :param medical_unit_type: the type of the medical unit - 1- ALS, 2- BLS , 3- motorcycle
    :return: topple {triage:_max_capacity}
    """
    max_capacity_dict = medical_unit_types_and_capacities[medical_unit_type]
    capacities = {key: value * max_capacity_dict[key] for key, value in triage.items()}
    return capacities


def get_skills_tuples(skills_activity, skills_triage):
    skills_set = [(key, item) for key in skills_activity
                    for item in skills_triage.keys() if skills_triage[item] > 0]
    return skills_set


def get_nearest_entity_location(other_entity, entities):
    """
    get location and list of entities  return the location of the nearest one
    :param location: an entity location
    :param entities: list of entities
    :return: the nearest location
    """
    min_distance = math.inf
    location = [0.0, 0.0]
    for entity in entities:
        dis = entity.distance_from_other_entity(other_entity)
        if dis < min_distance:
            location = copy.copy(entity.location)
            min_distance = dis
    return location
