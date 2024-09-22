import copy
import math

from Solver.SOMAOP.BasicSOMAOP import *
from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
from Simulator.SimulationComponents import ServiceProvider
from Solver.SOMAOP.BasicSOMAOP import SR, SP

dbug = True
BIG = 99999


class FmcSR(SR):
    def __init__(self, simulation_entity: ServiceRequester, bid_type, t_now=None, algo_version=0,repetitive = False):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=bid_type, t_now=t_now,
                    algorithm_version=algo_version)
        self.small = 0.001
        self.dPrice = {}  # The stabilization index
        self.arrival_time = {}  # vector of earliest times [skill]
        self.stable = False
        self.repetitive = repetitive

        #### local view
        # self.neighbors = self.neighbors 'A'
        self.allocations = {}  # matrices of allocations [sp*skill] 'X'
        self.bids = {}  # matrices of  bids [sp*skill] 'B'
        self.price = {}  # {skill : price } 'P'
        self.earliestTimes = {}  # matrices of earliest times [sp*skill] ''
        self.type = 'HSM'
        self.skills = list(self.skills_needed.keys())
        self.first = {}
        self.Rs = {}
        self.initial_offers = {}
        self.allocations_cap = {}
        self.max_cap_sp = copy.copy(simulation_entity.max_required)
        self.cap_sp = {}
        self.mp = 0.4

    def initialize(self):
        pass

    ####################################### msgs
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        if mail_in['type'] == 'R':
            self.type = 'R'
            self.Rs[msg.sender] = mail_in['bids']
        elif mail_in['type'] == 'SM':
            if self.type != 'R':
                self.type = 'SM'
        if 'earliestTimes' in mail_in: self.earliestTimes[msg.sender] = mail_in['earliestTimes']
        if 'first' in mail_in: self.first[msg.sender] = mail_in['first']
        if 'bids' in mail_in: self.bids[msg.sender] = mail_in['bids']

    def send_msgs(self):

        for sp in self.neighbors:
            mail_out = {}
            if sp in self.allocations: mail_out['allocation'] = self.allocations[sp]
            # if sp in self.allocations_cap : mail_out['allocation_cap'] = self.allocations_cap[sp]
            if sp in self.earliestTimes:
                mail_out['startTime'] = {}
                for skill in self.earliestTimes[sp].keys():
                    mail_out['startTime'][skill] = self.arrival_time[skill]
            if sp in self.commit.keys():
                mail_out['commit'] = self.commit[sp]
            elif self.type == 'HSM':
                mail_out['offers'] = self.initial_offers
                mail_out['skills'] = self.skills_needed
                mail_out['location'] = self.location

            if self.type == 'R': self.type = 'SM'
            if mail_out:
                mail_out['type'] = self.type
                self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))

        # if self.type == 'commit':
        #     for sp in self.arrival_time.keys():
        #         if sp in self.allocations:

        #         if sp in self.commit.keys():mail_out['commit'] = self.commit[sp]
        #         self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))

        self.earliestTimes = {}
        self.first = {}
        self.bids = {}

    ##################################### compute
    def compute(self):
        self.compute_price()
        self.compute_allocations()
        # self.compute_allocations_cap()
        self.compute_earliestTimes()
        self.check_if_it_stable()
        self.reset_view()

    def compute_price(self):
        if self.type == "R":
            self.bids = self.Rs
        self.dPrice = copy.deepcopy(self.price)
        self.price = {}
        for sp in self.bids.keys():
            for skillBid in self.bids[sp].keys():
                if skillBid in self.skills:
                    if skillBid in self.price.keys():
                        # if self.msg_type == 'commit':self.bids[sp][skillBid] = self.Rs[sp][skillBid]
                        self.price[skillBid] += self.bids[sp][skillBid]
                        self.cap_sp[skillBid] += 1
                    else:
                        self.price[skillBid] = self.bids[sp][skillBid]
                        self.cap_sp[skillBid] = 1
            self.NCLO += super().number_of_comparisons(1, len(self.bids))

    def compute_allocations(self):
        self.allocations = {}
        # e_skill = {skill: self.mp * (math.exp(1 - self.max_cap_sp[skill] / self.cap_sp[skill])) / self.cap_sp[skill] for
        #            skill in self.cap_sp}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
                # self.NCLO += 1
                if self.bids[sp][skill] != 0 and skill in self.skills:
                    allocation = self.bids[sp][skill] / self.price[skill]
                    # if allocation > e_skill[skill]:
                    if allocation > self.small:
                        if sp not in self.allocations: self.allocations[sp] = {}
                        self.allocations[sp][skill] = allocation
            self.NCLO += super().number_of_comparisons(1, len(self.bids))

    def compute_allocations_cap(self):
        self.allocations_cap = {}

        allocations_by_skill = {}
        for sp in self.allocations.keys():
            for skill in self.allocations[sp].keys():
                if skill not in allocations_by_skill: allocations_by_skill[skill] = []
                allocations_by_skill[skill].append({'sp': sp,
                                                    'allocation': self.allocations[sp][skill],
                                                    'value': self.allocations[sp][skill] * self.Rs[sp][skill] /
                                                             self.skills_needed[skill]})

        for skill in allocations_by_skill.keys():
            allocations_by_skill[skill] = sorted(allocations_by_skill[skill],
                                                 key=lambda allocation: allocation['value'], reverse=True)
            if len(allocations_by_skill[skill]) > self.max_cap_sp[skill]:
                allocations_by_skill[skill] = allocations_by_skill[skill][:self.max_cap_sp[skill]]

            sub_price = sum([allocation['allocation'] for allocation in allocations_by_skill[skill]])
            for allocation in allocations_by_skill[skill]:
                if allocation['sp'] not in self.allocations_cap: self.allocations_cap[allocation['sp']] = {}
                self.allocations_cap[allocation['sp']][skill] = allocation['allocation'] / sub_price

    def compute_earliestTimes(self):
        self.arrival_time = {}
        for sp in self.earliestTimes.keys():
            for skill in self.earliestTimes[sp].keys():
                if skill in self.arrival_time.keys():
                    if self.earliestTimes[sp][skill] > self.arrival_time[skill]:
                        self.arrival_time[skill] = self.earliestTimes[sp][skill]
                else:
                    self.arrival_time[skill] = self.earliestTimes[sp][skill]

            self.NCLO += super().number_of_comparisons(1, len(self.arrival_time))

    def compute_initial_offers(self):
        offers = {}
        for skill in self.skills_needed:
            offers[skill] = VariableAssignment(
                provider=None,
                requester=self,
                skill=skill,
                location=self.location,
                amount=None,
                duration=0.0,
                arrival_time=None,
                leaving_time=None,
                utility=None,
                mission=None,
                max_capacity=None,
                accept=False)
        self.initial_offers = offers

    def check_if_it_stable(self):
        self.commit = {}
        if not self.dPrice: return
        for skill in self.dPrice:
            if skill in self.price:
                if abs(self.dPrice[skill] - self.price[skill]) > self.small:
                    self.stable = False
                    return
        if not self.repetitive:
            self.stable = True  ####################
            return  #############################

        true_skill = []
        false_skill = []
        for sp in self.first.keys():
            for skill in self.first[sp].keys():
                if skill not in false_skill and skill in self.skills:
                    if self.first[sp][skill]:
                        if skill not in true_skill:
                            true_skill.append(skill)
                    else:
                        if skill in true_skill:
                            true_skill.remove(skill)
                        false_skill.append(skill)
        if true_skill:
            self.skills.remove(true_skill[0])
            self.type = 'commit'
            for sp in self.first.keys():
                self.commit[sp] = true_skill[0]

    def reset_view(self):
        self.bids = {}
        self.allocations_keys = copy.copy(list(self.allocations.keys()))


class FmcSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, algo_version=0, accept_offers_version=0,
                 alfa=0.7,repetitive = False):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=algo_version)
        self.raf = 0.001  # xij<e
        self.R = {}  # {SR_id:VALUE}
        self.skills = simulation_entity.skills  ## list of all the needed skills
        self.repetitive = repetitive

        self.srs = {}  ## list of all the sr that ask for a service { 'id' : id , 'skill': W(SR,skill) ,'location': location}
        self.offers = {}
        self.last_time = self.t_now
        self.old_schedule = []
        self.msg_tips = {}
        self.schedule = []
        self.first = None

        self.bids = {}  # matrices of  bids [sr*skill]
        self.arrival_times = {}

        self.allocations = {}  # matrices of allocations [sr*skill]
        self.allocations_cap = {}
        self.normalize = {}
        self.join_arrival_times = {}  # matrices of earliest times [sr*skill]
        self.commits = {}
        self.msg_typs = {}
        self.earliestTimes = {}
        self.final_schedule = []
        self.startTime = {}
        self.commits = {}
        self.old_final_schedule = []
        self.type = 'HSM'
        self.is_stable = 0

    def initialize(self):
        pass

    ############################################ msges
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        if 'allocation' in mail_in.keys():
            self.allocations[msg.sender] = mail_in['allocation']
        # if 'allocation_cap' in mail_in:self.allocations_cap[msg.sender] = mail_in['allocation_cap']
        if 'startTime' in mail_in.keys(): self.startTime[msg.sender] = mail_in['startTime']
        if 'commit' in mail_in: self.commits[msg.sender] = mail_in['commit']
        if mail_in['type'] == 'HSM':
            self.srs[msg.sender] = {'skills': self.filter_skills(mail_in['skills']),
                                    'location': mail_in['location'],
                                    'offers': mail_in['offers']}

        self.type = mail_in['type']

    def send_msgs(self):

        firsts = {}
        for offer in self.final_schedule:
            if offer.requester not in firsts.keys(): firsts[offer.requester] = {}
            if self.first is None:
                firsts[offer.requester][offer.skill] = False
            else:
                firsts[offer.requester][offer.skill] = (self.first == offer)

        for sr in self.neighbors:
            mail_out = {}
            if self.type == 'HSM':
                if sr in self.R: mail_out['bids'] = self.R[sr]
            elif self.type == 'SM':
                if sr in self.bids: mail_out['bids'] = self.bids[sr]
                if sr in self.earliestTimes: mail_out['earliestTimes'] = self.earliestTimes[sr]
                if sr in firsts: mail_out['first'] = firsts[sr]

            if mail_out:
                if self.type == 'HSM':
                    mail_out['type'] = 'R'
                elif self.type == 'SM':
                    mail_out['type'] = 'SM'
                self.mailer.send_msg(OfferMessage(self._id, sr, mail_out))
        self.allocations = {}
        self.type = 'SM'

    ############################################# compute
    def compute(self):
        if self.type == 'SM': self.compute_bid()
        self.create_initial_schedule()
        # self.is_commit()
        self.calculate_start_and_end_times()
        self.compute_R()
        self.reset_view()

    def compute_bid(self):

        self.bids = {}
        sumXS = {}
        for sr in self.allocations.keys():
            for skill in self.allocations[sr].keys():
                if skill in self.skills:
                    if skill in sumXS:
                        sumXS[skill] += self.allocations[sr][skill] * self.R[sr][skill]
                    else:
                        sumXS[skill] = self.allocations[sr][skill] * self.R[sr][skill]

        for sr in self.allocations.keys():
            for skill in self.allocations[sr].keys():
                if skill in self.skills:
                    if sumXS[skill] != 0:
                        if sr not in self.bids: self.bids[sr] = {}
                        self.bids[sr][skill] = self.allocations[sr][skill] * self.R[sr][skill] / sumXS[skill]
            self.NCLO += 2 * super().number_of_comparisons(1, len(self.allocations))

    def create_initial_schedule(self):
        self.schedule = []
        for sr in self.allocations.keys():
            for skill in self.allocations[sr].keys():
                self.schedule.append(SPSchedule(
                    self,
                    sr,
                    skill,
                    self.last_time,
                    # self.last_time+self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    self.last_time + self.allocations[sr][skill] * self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    ########      W(SR,SKILL),
                    (self.bids[sr][skill] / self.srs[sr]['skills'][skill]),
                    self.allocations[sr][skill]))

            self.NCLO += super().number_of_comparisons(1, len(self.allocations))

        self.schedule = sorted(self.schedule, key=lambda sp_schedule: sp_schedule.important)
        # old_location = self.location
        # time = 0
        for i in range(len(self.schedule)):
            sp_ = self.schedule[i]
            if i == 0:
                sp_.update_startTime(self.last_time + sp_.travel_from())
            else:
                sp_.update_startTime(self.schedule[i - 1].leaving_time + sp_.travel_from(self.schedule[i - 1]))

            # length = sp_.leaving_time - sp_.arrival_time
            # time += self.travel_time(old_location,sp_.location) + length
            if sp_.requester not in self.earliestTimes: self.earliestTimes[sp_.requester] = {}
            self.earliestTimes[sp_.requester][sp_.skill] = sp_.arrival_time
            self.NCLO += super().number_of_comparisons(1, len(self.allocations))

            # old_location = sp_.location
        self.final_schedule = self.schedule

    def calculate_start_and_end_times(self):
        schedule_cooperative = []
        schedule_uncooperative = []
        if not self.old_schedule:
            self.final_schedule = []
        else:
            for sp_schedule in self.old_schedule:
                if round(sp_schedule.allocation, 4) <= 1:  ################   if cooperative

                    sp_schedule.update_startTime(self.startTime[sp_schedule.requester][sp_schedule.skill])
                    sp_schedule.p_arrival_time = sp_schedule.arrival_time
                    schedule_cooperative.append(sp_schedule)
                    continue

                schedule_uncooperative.append(sp_schedule)
            schedule_cooperative = sorted(schedule_cooperative, key=lambda sp_schedule: sp_schedule.arrival_time)
            if schedule_cooperative: e_allocation = schedule_cooperative[0]
            for l_allocation in schedule_cooperative:
                if l_allocation == e_allocation: continue
                travel_time = e_allocation.travel_to(l_allocation)
                distant_time = l_allocation.arrival_time - e_allocation.leaving_time - travel_time
                if distant_time < 0:
                    l_allocation.update_startTime(e_allocation.leaving_time + travel_time)
                    # l_allocation.update_startTime(l_allocation.p_arrival_time)
                    schedule_uncooperative.append(l_allocation)
                    schedule_cooperative.remove(l_allocation)
                    self.earliestTimes[l_allocation.requester][l_allocation.skill] = l_allocation.arrival_time
                e_allocation = l_allocation

            schedule_uncooperative = sorted(schedule_uncooperative, key=lambda sp_schedule: sp_schedule.arrival_time)
            # self.final_schedule = schedule_cooperative + schedule_uncooperative
            schedule_uncooperative_left = copy.copy(schedule_uncooperative)

            for un_allocation in schedule_uncooperative:
                if schedule_cooperative: e_co_allocation = schedule_cooperative[0]
                for co_allocation in schedule_cooperative:
                    if co_allocation == e_co_allocation:
                        distant_time = co_allocation.arrival_time - self.last_time
                        sub_distant_time = (un_allocation.leaving_time - un_allocation.arrival_time
                                            + un_allocation.travel_from() + un_allocation.travel_to(co_allocation))
                    else:
                        distant_time = co_allocation.arrival_time - e_co_allocation.leaving_time
                        sub_distant_time = (un_allocation.leaving_time - un_allocation.arrival_time
                                            + un_allocation.travel_from(e_co_allocation) + un_allocation.travel_to(
                                    co_allocation))

                    if sub_distant_time < distant_time:
                        un_allocation.update_startTime(
                            e_co_allocation.leaving_time + un_allocation.travel_from(e_co_allocation))
                        schedule_cooperative.insert(schedule_cooperative.index(co_allocation) + 1, un_allocation)
                        e_co_allocation = un_allocation
                        schedule_uncooperative_left.remove(un_allocation)
                        break
                    e_co_allocation = co_allocation
            if schedule_cooperative:
                e_allocation = schedule_cooperative[-1]
            else:
                e_allocation = None
            for allocation in schedule_uncooperative_left:
                if e_allocation is None:
                    allocation.update_startTime(self.last_time + allocation.travel_from())
                else:
                    allocation.update_startTime(e_allocation.leaving_time + allocation.travel_from(e_allocation))
                e_allocation = allocation

            self.final_schedule = schedule_cooperative + schedule_uncooperative_left
            # print('lemgth', " : ", len(self.old_final_schedule), " : ", len(self.final_schedule), " : ",
            #       len(self.old_final_schedule + self.final_schedule))

    def compute_R(self):  # fl     חישוב הR

        if self.type == 'HSM':
            for sr in self.srs.keys():
                for skill in self.srs[sr]['skills'].keys():
                    offer = self.srs[sr]['offers'][skill]
                    offer.provider = self
                    offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)
                    offer.amount = 10
                    offer.leaving_time = self.last_time + BIG
                    offer.accept = True
                    if sr not in self.offers: self.offers[sr] = {}
                    self.offers[sr][skill] = offer
                self.NCLO += super().number_of_comparisons(1, len(self.srs))

        for sr in self.commits.keys():
            if sr == self.first.requester and self.commits[sr] == self.first.skill:
                self.type = 'HSM'
                self.commit(self.first)
                break

                # self.commit(sr, self.commits[sr])

        if self.type == 'HSM':
            Rs = {}
            self.R = {}
            for sr in self.offers.keys():
                for skill in self.offers[sr].keys():
                    offer = self.offers[sr][skill]
                    if sr not in self.R: self.R[sr] = {}
                    self.R[sr][skill] = offer.requester.simulation_entity.calc_converge_bid_to_offer(skill, offer)
                    if skill not in Rs:
                        Rs[skill] = self.R[sr][skill]
                    else:
                        Rs[skill] += self.R[sr][skill]
                self.NCLO += super().number_of_comparisons(1, len(self.offers))

            for sr in self.R.keys():
                for skill in self.R[sr].keys():
                    if Rs[skill] != 0:
                        self.R[sr][skill] = self.R[sr][skill] / Rs[skill]

    ########################################### sub function
    def reset_view(self):
        # self.startTime = {}
        self.allocations = {}
        self.allocations_cap = {}
        self.old_schedule = copy.copy(self.schedule)
        # if self.is_stable>1:
        if self.final_schedule:
            self.first = self.final_schedule[0]
        else:
            self.first = None
        # else:self.is_stable+=1
        self.commits = {}

    def filter_skills(self, skills):
        new_skills = {}
        for skill in skills.keys():
            if skill in self.skills:
                new_skills[skill] = skills[skill]
        return new_skills

    def get_schedule(self):
        return self.old_final_schedule + self.final_schedule

    def commit(self, first):
        self.old_final_schedule.append(first)
        self.offers[first.requester].pop(first.skill)
        if not self.offers[first.requester]: self.offers.pop(first.requester)

        self.location = first.location
        self.last_time = first.leaving_time

        for sp in self.offers:
            for skill in self.offers[sp]:
                offer = self.offers[sp][skill]
                offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)


class SPSchedule(VariableAssignment):
    def __init__(self, sp, sr, skill, arrival_time, leaving_time, important, allocation):
        VariableAssignment.__init__(self,
                                    provider=sp,
                                    requester=sr,
                                    skill=skill,
                                    location=sp.srs[sr]['location'],
                                    amount=None,
                                    duration=0.0,
                                    arrival_time=None,
                                    leaving_time=None,
                                    utility=None,
                                    mission=None,
                                    max_capacity=None,
                                    accept=True
                                    )

        # self.skill = skill
        # self.sp = sp
        # self.id = sr

        self.allocation = allocation
        travel_time = self.travel_from()
        self.travel_time = travel_time
        self.arrival_time = arrival_time + travel_time
        self.leaving_time = leaving_time
        self.important = important
        self.location = sp.srs[sr]['location']

    def __repr__(self):
        return f'sp :  {self.provider} sr : {self.requester} skill : {self.skill} startTime :  {self.arrival_time}'

    def update_startTime(self, new_star_time):
        self.leaving_time = new_star_time + self.leaving_time - self.arrival_time
        self.arrival_time = new_star_time
        self.travel_time = None

    def travel_to(self, to):
        return self.provider.travel_time(self.location, to.location)

    def travel_from(self, from_=None):
        if from_ is None:
            return self.provider.travel_time(self.provider.location, self.location)
        else:
            return self.provider.travel_time(from_.location, self.location)
