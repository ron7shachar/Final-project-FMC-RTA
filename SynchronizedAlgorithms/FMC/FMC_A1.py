import copy
import math

from Solver.SOMAOP.BasicSOMAOP import *
from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
from Simulator.SimulationComponents import ServiceProvider
from Solver.SOMAOP.BasicSOMAOP import SR, SP

dbug = True
BIG = 99999


class FmcSR(SR):
    def __init__(self, simulation_entity: ServiceRequester, t_now=None, repetitive=False,
                 max_iterations=500, mp=0.2):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=0, t_now=t_now,
                    algorithm_version=0)

        # constant
        self.max_iterations = max_iterations
        self.small = 0.01
        self.mp = mp
        #  variables
        self.depth = 0
        self.dPrice = {}  # The stabilization index
        self.price = {}  # {skill : price } 'P'
        self.stable = False
        self.repetitive = repetitive
        self.type = 'HSM'
        self.skills = list(self.skills_needed.keys())
        self.max_cap_sp = copy.copy(simulation_entity.max_required)
        self.cap_sp = {}
        self.Rs = {}

        #### local view
        # self.neighbors = self.neighbors 'A'
        self.bids = {}  # matrices of  bids [sp*skill] 'B'
        self.earliestTimes = {}  # matrices of earliest times [sp*skill] ''
        self.first = {}

        #### to msg
        self.allocations = {}  # matrices of allocations [sp*skill] 'X'
        self.allocations_cap = {}
        self.arrival_time = {}  # vector of earliest times [skill]
        self.initial_offers = {}
        self.commit = {}

    def initialize(self):
        pass

    ####################################### msgs
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        if mail_in['type'] == 'R':
            self.type = 'R'
            if 'bids' in mail_in:self.Rs[msg.sender] = mail_in['bids']
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
            if sp in self.allocations_cap : mail_out['allocation_cap'] = self.allocations_cap[sp]
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

        self.reset_view()

    ##################################### compute
    def compute(self):
        self.compute_price()
        self.compute_allocations()
        self.compute_earliestTimes()
        self.check_if_it_stable()
        self.compute_allocations_cap()

    def compute_price(self):
        if self.type == "R":
            self.bids = self.Rs
        self.price = {}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
                if skill in self.skills:
                    if skill in self.price.keys():
                        self.price[skill] += self.bids[sp][skill]
                        self.cap_sp[skill] += 1
                    else:
                        self.price[skill] = self.bids[sp][skill]
                        self.cap_sp[skill] = 1
            self.NCLO += super().number_of_comparisons(1, len(self.bids))

    def compute_allocations(self):
        self.allocations = {}
        # e_skill = {skill:max([self.mp,self.depth/self.max_iterations]) * (math.exp(1 - self.max_cap_sp[skill] / self.cap_sp[skill])) / self.cap_sp[skill] for
        #            skill in self.cap_sp}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
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
                if skill in self.skills:
                    if skill not in allocations_by_skill: allocations_by_skill[skill] = []
                    allocations_by_skill[skill].append({'sp': sp,
                                                        'allocation': self.allocations[sp][skill],
                                                        'value': self.allocations[sp][skill]})
                                                        # 'value': self.allocations[sp][skill] * self.Rs[sp][skill] /
                                                        #          self.skills_needed[skill]})

        for skill in allocations_by_skill.keys():
            allocations_by_skill[skill] = sorted(allocations_by_skill[skill],
                                                 key=lambda allocation: allocation['value'], reverse=True)
            if len(allocations_by_skill[skill]) > self.max_cap_sp[skill]:
                allocations_by_skill[skill] = allocations_by_skill[skill][:self.max_cap_sp[skill]]
            sub_price = sum([allocation['allocation'] for allocation in allocations_by_skill[skill]])
            # sub_price = 1/len(allocations_by_skill[skill])
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
        if self.depth < 3:
            return
        for skill in self.dPrice:
            if skill in self.price:
                if abs(self.dPrice[skill] - self.price[skill]) > self.small:
                    self.stable = False
                    return
        if not self.repetitive:
            self.stable = True
            return

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
            print(f'commit SR {self._id}  and skill {true_skill[0]} ')
            self.type = 'commit'
            print(self._id , true_skill[0],self.skills)
            self.depth = 0
            for sp in self.first.keys():
                self.commit[sp] = true_skill[0]
                # if true_skill[0] in self.allocations[sp]:
                #     self.allocations[sp].pop(true_skill[0])
                #     if not self.allocations[sp]:self.allocations.pop(sp)


    def reset_view(self):
        self.earliestTimes = {}
        self.first = {}
        self.bids = {}
        self.dPrice = copy.deepcopy(self.price)
        self.depth += 1


class FmcSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, repetitive=False):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=0.1)

        # constant
        self.repetitive = repetitive

        #  variables
        self.R = {}  # {SR_id:VALUE}
        self.skills = simulation_entity.skills  ## list of all the needed skills

        self.srs = {}  ## list of all the sr that ask for a service { 'id' : id , 'skill': W(SR,skill) ,'location': location}
        self.offers = {}
        self.last_time = self.t_now
        self.type = 'HSM'

        self.schedule = []
        self.old_schedule = []

        self.final_schedule = []
        self.old_final_schedule = []
        self.move = []
        self.depth = 0

        #### local view
        self.allocations = {}  # matrices of allocations [sr*skill]
        self.allocations_cap = {}
        self.commits = {}
        self.startTime = {}

        #### to msg
        self.first = None
        self.bids = {}  # matrices of  bids [sr*skill]
        self.earliestTimes = {}

    def initialize(self):
        pass

    ############################################ msges
    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
        if 'allocation' in mail_in.keys():
            self.allocations[msg.sender] = mail_in['allocation']
        if 'allocation_cap' in mail_in:self.allocations_cap[msg.sender] = mail_in['allocation_cap']
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
            if self.type == 'HSM' or self.type == "commit":
                if sr in self.R: mail_out['bids'] = self.R[sr]
            elif self.type == 'SM':
                if sr in self.bids: mail_out['bids'] = self.bids[sr]
            if sr in self.earliestTimes: mail_out['earliestTimes'] = self.earliestTimes[sr]
            if sr in firsts: mail_out['first'] = firsts[sr]

            if mail_out:
                if self.type == 'HSM'or self.type == "commit":
                    mail_out['type'] = 'R'
                elif self.type == 'SM':
                    mail_out['type'] = 'SM'
                self.mailer.send_msg(OfferMessage(self._id, sr, mail_out))
        self.allocations = {}
        self.type = 'SM'

    ############################################# compute
    def compute(self):
        if self.type == 'SM': self.compute_bid()
        self.is_commit()
        self.create_initial_schedule()
        self.calculate_start_and_end_times()
        self.check_schedule()
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
        # self.allocations_cap = self.allocations
        for sr in self.allocations_cap.keys():
            for skill in self.allocations_cap[sr].keys():
                self.schedule.append(SPSchedule(
                    self,
                    sr,
                    skill,
                    self.last_time,
                    # self.last_time+self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    self.last_time + self.allocations_cap[sr][skill] * self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    ########      W(SR,SKILL),
                    (self.bids[sr][skill] / self.srs[sr]['skills'][skill]),
                    self.allocations_cap[sr][skill]))

            self.NCLO += super().number_of_comparisons(1, len(self.allocations_cap))

        self.schedule = sorted(self.schedule, key=lambda sp_schedule: sp_schedule.important, reverse=True)
        if self.schedule: e_task = self.schedule[0]
        for task in self.schedule:
            if e_task == task:
                task.update_startTime(self.last_time + task.travel_from())
            else:
                task.update_startTime(e_task.leaving_time + task.travel_from(e_task))

            if task.requester not in self.earliestTimes.keys(): self.earliestTimes[task.requester] = {}
            self.earliestTimes[task.requester][task.skill] = task.arrival_time
            self.NCLO += super().number_of_comparisons(1, len(self.allocations_cap))
        # self.final_schedule = self.schedule

    def calculate_start_and_end_times(self):
        schedule_cooperative = []
        schedule_uncooperative = []
        overlap_task = []
        if not self.old_schedule:
            self.final_schedule = []
        else:
            for task in self.old_schedule:
                # if task.requester not in self.startTime: continue
                if task.allocation < 0.999999:  ################   if cooperative
                    if task.requester not in self.startTime.keys():
                        overlap_task.append(task)
                    else:
                        task.update_startTime(self.startTime[task.requester][task.skill])
                    task.p_arrival_time = task.arrival_time
                    schedule_cooperative.append(task)
                else:
                    schedule_uncooperative.append(task)

            schedule_cooperative = sorted(schedule_cooperative, key=lambda task: task.arrival_time)

            legal_schedule_cooperative = []
            if schedule_cooperative: e_task = schedule_cooperative[0]
            for l_task in schedule_cooperative:
                if l_task == e_task:
                    legal_schedule_cooperative.append(l_task)
                    continue
                travel_time = e_task.travel_to(l_task)
                distant_time = l_task.arrival_time - e_task.leaving_time - travel_time
                if distant_time < 0:
                    # l_task.update_startTime(e_task.leaving_time + travel_time)
                    l_task.update_startTime(l_task.p_arrival_time)
                    schedule_uncooperative.append(l_task)
                    overlap_task.append(l_task)
                else:
                    legal_schedule_cooperative.append(l_task)
                    e_task = l_task
            schedule_uncooperative = sorted(schedule_uncooperative, key=lambda task: task.arrival_time)
            schedule_uncooperative_left = copy.copy(schedule_uncooperative)

            for un_task in schedule_uncooperative:
                if legal_schedule_cooperative: e_co_task = legal_schedule_cooperative[0]
                for co_task in legal_schedule_cooperative:
                    if co_task == e_co_task:
                        distant_time = co_task.arrival_time - self.last_time
                        sub_distant_time = (un_task.leaving_time - un_task.arrival_time
                                            + un_task.travel_from() + un_task.travel_to(co_task))
                    else:
                        distant_time = co_task.arrival_time - e_co_task.leaving_time
                        sub_distant_time = (un_task.leaving_time - un_task.arrival_time
                                            + un_task.travel_from(e_co_task) + un_task.travel_to(
                                    co_task))

                    if sub_distant_time < distant_time:
                        if co_task == e_co_task:
                            un_task.update_startTime(
                                self.last_time + un_task.travel_from())
                        else:
                            un_task.update_startTime(
                                e_co_task.leaving_time + un_task.travel_from(e_co_task))

                        legal_schedule_cooperative.insert(legal_schedule_cooperative.index(co_task), un_task)
                        schedule_uncooperative_left.remove(un_task)

                        break
                    e_co_task = co_task

            if legal_schedule_cooperative:
                e_task = legal_schedule_cooperative[-1]
            else:
                e_task = None
            for task in schedule_uncooperative_left:
                if e_task is None:
                    task.update_startTime(self.last_time + task.travel_from())
                else:
                    task.update_startTime(e_task.leaving_time + task.travel_from(e_task))
                e_task = task

            for task in overlap_task:
                self.earliestTimes[task.requester][task.skill] = task.arrival_time

            self.final_schedule = sorted(legal_schedule_cooperative + schedule_uncooperative_left,
                                         key=lambda task: task.arrival_time)
            # if self.repetitive:
                # print('lemgth', " : ", len(self.old_final_schedule), " : ", len(self.final_schedule), " : ",
                #       len(self.old_final_schedule + self.final_schedule))
            if len(self.final_schedule)!=len(self.old_schedule):
                print(f'len: {len(self.final_schedule)} , {len(self.old_schedule)}')


    def is_commit(self):
        if self.first is not None:
            for sr, commit in self.commits.items():
                if sr == self.first.requester and commit == self.first.skill:
                    # self.type = 'HSM'
                    self.commit(self.first)
                    break
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


        if self.type == 'HSM' or self.type == "commit":
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

        if self.type != "commit" and self.move :
            self.old_final_schedule.append(self.move[0])
            self.move.pop(0)

        self.allocations = {}
        self.allocations_cap = {}
        self.old_schedule = copy.copy(self.schedule)
        self.schedule = []
        if self.final_schedule and not self.move:
            self.first = self.final_schedule[0]
        else:
            self.first = None
        self.commits = {}
        self.startTime = {}
        self.depth += 1

    def filter_skills(self, skills):
        new_skills = {}
        for skill in skills.keys():
            if skill in self.skills:
                new_skills[skill] = skills[skill]
        return new_skills

    def get_schedule(self):
        return self.old_final_schedule + self.final_schedule

    def commit(self, first):
        print(f'sp {self._id} commit to sr {first.requester} skill {first.skill}')
        self.move.append(first)



        self.offers[first.requester].pop(first.skill)
        if not self.offers[first.requester]: self.offers.pop(first.requester)

        self.location = first.location
        self.last_time = first.leaving_time

        self.type = 'commit'

        for sp in self.offers:
            for skill in self.offers[sp]:
                offer = self.offers[sp][skill]
                offer.arrival_time = self.last_time + self.travel_time(self.location, offer.location)



    def check_schedule(self):
        schedule = self.get_schedule()
        if schedule: o_task = schedule[0]
        for task in schedule:
            if o_task != task:
                if o_task.leaving_time > task.arrival_time - o_task.travel_to(task) +0.000001:
                    raise IllegalScheduleError(
                        '\033[31m' + ' error in schedule' + '\033[0m' + f'{o_task} : T0 {o_task.leaving_time} and {task}  : TN {task.arrival_time - o_task.travel_to(task)}')

    def isStable(self):
        return (not self.final_schedule and self.depth > 2)











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
        self.arrival_time = arrival_time + travel_time
        self.leaving_time = leaving_time + travel_time
        self.important = important
        self.location = sp.srs[sr]['location']

    def __repr__(self):
        return f'sp :  {self.provider} sr : {self.requester} skill : {self.skill} startTime :  {self.arrival_time} allocation: {self.allocation}'


    def update_startTime(self, new_star_time):
        self.leaving_time = new_star_time + self.leaving_time - self.arrival_time
        self.arrival_time = new_star_time

    def travel_to(self, to):
        return self.provider.travel_time(self.location, to.location)

    def travel_from(self, from_=None):
        if from_ is None:
            return self.provider.travel_time(self.provider.location, self.location)
        else:
            return self.provider.travel_time(from_.location, self.location)

class IllegalScheduleError(Exception):
    """Exception raised for errors in the schedule."""
    def __init__(self, message="The schedule is illegal"):
        self.message = message
        super().__init__(self.message)