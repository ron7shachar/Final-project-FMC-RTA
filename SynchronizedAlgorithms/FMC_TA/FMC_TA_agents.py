import copy
import math

from Solver.SOMAOP.BasicSOMAOP import *
from SynchronizedAlgorithms.SynchronizedSolver import VariableAssignment
from Simulator.SimulationComponents import ServiceProvider
from Solver.SOMAOP.BasicSOMAOP import SR, SP

class FmcSR(SR):
    def __init__(self, simulation_entity: ServiceRequester, bid_type = 0,t_now=None, repetitive=False,
                 min_work_split = 0.01,e = 0.001 ):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SR.__init__(self, simulation_entity=simulation_entity, bid_type=bid_type , t_now=t_now,
                    algorithm_version=0)

        # constant
        self.min_work_split = min_work_split #the smallest division of a task
        self.e = e # the stability resolution
        self.repetitive = repetitive # version repetitive: bool

        #  variables
        self.dPrice = {}  # The stabilization index/ i-1 price
        self.price = {}  # {skill : price } 'P'
        self.stable = False # for the un-repetitive version
        self.type = 'HSM' # the message states type :'HSM' [out] , 'SM' [in,out] , "R" [in], 'commit' [out]
        self.skills = list(self.skills_needed.keys()) # skills needed
        self.max_cap_sp = copy.copy(simulation_entity.max_required) # max cap :{skill : int }




        #### local view
        # self.neighbors = self.neighbors 'A'
        self.bids = {}  # matrices of  bids [sp*skill] 'B'
        self.earliestTimes = {}  # matrices of earliest times [sp*skill] ''
        self.first = {} # matrices of first tasks [sp*skill] = bool

        #### to msg
        self.allocations = {}  # matrices of allocations [sp*skill] 'X'
        self.allocations_cap = {} # normalize matrices of the allocations [max_cap*skill] 'X_cap'
        self.arrival_time = {}  # dict of earliest times [skill]
        self.initial_offers = {} # dict[skill] = initial_offer  :if self.type == 'HSM'
        self.commit = {} # dict[sp] = skill  : if self.type == commit

    def initialize(self):
        pass

    ####################################### msgs

    def agent_receive_a_single_msg(self, msg):
        mail_in = msg.information
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
                mail_out['time_skills'] = self.simulation_entity.time_per_skill_unit
                mail_out['location'] = self.location

            else: self.type = 'SM'
            if mail_out:
                mail_out['type'] = self.type
                self.mailer.send_msg(OfferMessage(self._id, sp, mail_out))

        self.reset_view()

    ##################################### compute
    def compute(self):
        self.compute_price()
        self.compute_allocations()
        self.compute_startTime()
        self.check_if_it_stable()
        self.compute_allocations_cap()
        self.compute_NCLO()




    def compute_price(self):

        self.price = {}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
                if skill in self.skills:
                    if skill in self.price.keys():
                        self.price[skill] += self.bids[sp][skill]
                    else:
                        self.price[skill] = self.bids[sp][skill]



    def compute_allocations(self):
        self.allocations = {}
        for sp in self.bids.keys():
            for skill in self.bids[sp].keys():
                if self.bids[sp][skill] != 0 and skill in self.skills:
                    allocation = self.bids[sp][skill] / self.price[skill]
                    if allocation > self.min_work_split:
                        if sp not in self.allocations: self.allocations[sp] = {}
                        self.allocations[sp][skill] = allocation


    def compute_startTime(self):
        self.arrival_time = {}
        for sp in self.earliestTimes.keys():
            for skill in self.earliestTimes[sp].keys():
                if skill in self.arrival_time.keys():
                    if self.earliestTimes[sp][skill] > self.arrival_time[skill]:
                        self.arrival_time[skill] = self.earliestTimes[sp][skill]
                else:
                    self.arrival_time[skill] = self.earliestTimes[sp][skill]


    def check_if_it_stable(self):
        self.commit = {}
        # check if the prises is stable
        for skill in self.dPrice:
            if skill in self.price:
                if abs(self.dPrice[skill] - self.price[skill]) > self.e:
                    self.stable = False
                    return
        if not self.repetitive and self.dPrice:
            self.stable = True
            return

        # check if it is the first task
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

        if true_skill:# if first creat 'commit '
            self.skills.remove(true_skill[0])
            print(f' commit:  SR {self._id} | skill {true_skill[0]} ')
            for sp in self.first.keys():
                self.commit[sp] = true_skill[0]

    def compute_allocations_cap(self):
        self.allocations_cap = {}
        allocations_by_skill = {}
        # create allocations by skill
        for sp in self.allocations.keys():
            for skill in self.allocations[sp].keys():
                if skill in self.skills:
                    if skill not in allocations_by_skill: allocations_by_skill[skill] = []
                    allocations_by_skill[skill].append({'sp': sp,
                                                        'allocation': self.allocations[sp][skill],
                                                        'value': self.allocations[sp][skill]})

        # filter the best max cap options
        skills_needed = self.skills_needed.copy()
        for skill in allocations_by_skill.keys():
            allocations_by_skill[skill] = sorted(allocations_by_skill[skill],
                                                 key=lambda allocation: allocation['value'], reverse=True)
            if len(allocations_by_skill[skill]) > self.max_cap_sp[skill]:
                allocations_by_skill[skill] = allocations_by_skill[skill][:self.max_cap_sp[skill]]
            sub_price = sum([allocation['allocation'] for allocation in allocations_by_skill[skill]])

            # normalize the subtask skills
            for allocation in allocations_by_skill[skill]:
                if allocation['sp'] not in self.allocations_cap: self.allocations_cap[allocation['sp']] = {}
                # self.allocations_cap[allocation['sp']][skill] = allocation['allocation'] / sub_price
                part = abs(allocation['allocation']*self.skills_needed[skill]/ sub_price)
                delta = part - skills_needed[skill]
                if delta > 0 and delta < part:
                        part = skills_needed[skill]
                        self.allocations_cap[allocation['sp']][skill] = part, part * \
                                                                              self.simulation_entity.time_per_skill_unit[skill]
                        break
                skills_needed[skill] -= part
                self.allocations_cap[allocation['sp']][skill] = part,part*self.simulation_entity.time_per_skill_unit[skill]




    # ############################## sub functions
    def reset_view(self):
        self.earliestTimes = {}
        self.first = {}
        self.bids = {}
        self.dPrice = copy.deepcopy(self.price)


    def compute_initial_offers(self):
        offers = {}
        for skill in self.skills_needed:
            offers[skill] = VariableAssignment(
                provider=None,
                requester=self,
                skill=skill,
                location=self.location,
                amount=None,
                duration=1000,
                arrival_time=None,
                leaving_time=None,
                utility=None,
                mission=None,
                max_capacity=None,
                accept=False)
        self.initial_offers = offers

    def compute_NCLO(self):
        in_ = max(len(self.bids),len(self.earliestTimes),len(self.first))
        out_ = max(len(self.allocations),len(self.allocations_cap),len(self.arrival_time),len(self.initial_offers),len(self.commit))
        if self.type == 'HSM':in_ = len(self.neighbors)
        self.NCLO += super().number_of_comparisons(out_, in_)


class FmcSP(SP):
    def __init__(self, simulation_entity: ServiceProvider, t_now=None, repetitive=False,updated_heuristic = True):
        if t_now is None: t_now = simulation_entity.last_time_updated
        SP.__init__(self, simulation_entity=simulation_entity, t_now=t_now, algorithm_version=0.1)

        # constant
        self.repetitive = repetitive # version repetitive: bool
        self.updated_heuristic = updated_heuristic #use the updated heuristic :bool

        #  variables
        self.R = {}  # {SR_id:VALUE}
        self.skills = simulation_entity.skills  ## list of all the needed skills
        self.skill_set
        print(self.skill_set)
        self.srs = {}  ## list of all the sr that ask for a service { 'id' : id , 'skill': W(SR,skill) ,'location': location}
        self.offers = {} # the needs of the sr subs skills
        self.free_start_time = self.t_now # the start unallocated time
        self.type = 'HSM' # the message states type :'HSM' [in] , 'SM' [in,out] , "R" [out], 'commit' [in]


        self.schedule = [] # list of SPSchedule
        self.old_schedule = [] # n-1 list of SPSchedule
        self.final_schedule = [] # list of the final uncommitted allocations [SPSchedule]
        self.committed_final_schedule = [] # list of the final committed allocations [SPSchedule]
        self.temporary_first = [] # hold the committed  task util the final schedule is updated
        self.depth = 0 # how many interaction from the last commit


        #### local view
        self.allocations = {}  # matrices of allocations [sr*skill]
        self.allocations_cap = {} # normalize matrices of the allocations [max_cap*skill] 'X'
        self.commits = {} #dict[sr] = skill
        self.arrival_time = {} # matrix of [sr*skill] = Time

        #### to msg
        self.first = None # the first task
        self.bids = {}  # matrices of  bids [sr*skill]
        self.earliestTimes = {} # matrices of  bids [sr*skill]

    def initialize(self):
        pass

    ############################################ msges
    def agent_receive_a_single_msg(self, msg):

        mail_in = msg.information
        if 'allocation' in mail_in.keys():
            self.allocations[msg.sender] = mail_in['allocation']
        if 'allocation_cap' in mail_in:self.allocations_cap[msg.sender] = mail_in['allocation_cap']
        if 'startTime' in mail_in.keys(): self.arrival_time[msg.sender] = mail_in['startTime']
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
                self.mailer.send_msg(OfferMessage(self._id, sr, mail_out))
        self.type = 'SM'

    ############################################# compute
    def compute(self):
        self.compute_bid()
        self.is_commit()
        self.create_initial_schedule()
        self.calculate_start_and_end_times()
        # self.check_schedule()
        self.compute_R()
        self.reset_view()
        self.compute_NCLO()



    def compute_bid(self):
        self.bids = {}
        sumXS = {}
        for sr in self.allocations.keys():
            for skill in self.allocations[sr].keys():
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

    def is_commit(self):
        if self.first is not None:
            for sr, commit in self.commits.items():
                if sr == self.first.requester and commit == self.first.skill:
                    self.commit(self.first)
                    break
    def create_initial_schedule(self):
        # craet the tasks
        self.schedule = []
        for sr,allocations in self.allocations_cap.items():
            for skill,  (part, work_time) in allocations.items():
                self.schedule.append(SPSchedule(
                    self,
                    sr,
                    skill,
                    self.free_start_time,
                    # self.free_start_time+self.srs[sr]['skills'][skill],  # fl זמן הפעולה
                    self.free_start_time + work_time,  # fl זמן הפעולה
                    ########      W(SR,SKILL),
                    (self.bids[sr][skill] / self.srs[sr]['skills'][skill]),
                    part))



        # order the tasks and update the times
        self.schedule = sorted(self.schedule, key=lambda sp_schedule: sp_schedule.important, reverse=True)


        self.schedule_ = []
        skills_amount = self.skill_set.copy()
        for task in self.schedule:
            amount = skills_amount[task.skill] - task.allocation
            if amount >= 0:
                self.schedule_.append(task)
                skills_amount[task.skill] = amount
            elif skills_amount[task.skill] != 0:
                task.leaving_time = task.arrival_time+((task.leaving_time - task.arrival_time)*task.allocation/skills_amount[task.skill])
                task.allocation = skills_amount[task.skill]
                self.schedule_.append(task)
                skills_amount[task.skill] = 0
        self.schedule = self.schedule_

        if self.schedule: e_task = self.schedule[0]
        for task in self.schedule:
            if e_task == task:
                task.update_startTime(self.free_start_time + task.travel_from())
            else:
                task.update_startTime(e_task.leaving_time + task.travel_from(e_task))
            if task.requester not in self.earliestTimes.keys(): self.earliestTimes[task.requester] = {}
            self.earliestTimes[task.requester][task.skill] = task.arrival_time

    def calculate_start_and_end_times(self):
        schedule_cooperative = []
        schedule_uncooperative = []
        overlap_task = []

        if not self.old_schedule:
            self.final_schedule = []
        else:
            # update the start time of the cooperative tasks to arrival_time
            for task in self.old_schedule:
                if task.allocation < 0.999999:  ################   if cooperative
                    if task.requester not in self.arrival_time.keys():
                        overlap_task.append(task)
                    else:
                        task.update_startTime(self.arrival_time[task.requester][task.skill])
                    task.p_arrival_time = task.arrival_time
                    schedule_cooperative.append(task)
                else:
                    schedule_uncooperative.append(task)

            schedule_cooperative = sorted(schedule_cooperative, key=lambda task: task.arrival_time)
            legal_schedule_cooperative = []
            if schedule_cooperative: e_task = schedule_cooperative[0]

            # solve a legal states
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
                    if self.updated_heuristic:overlap_task.append(l_task)
                else:
                    legal_schedule_cooperative.append(l_task)
                    e_task = l_task
            schedule_uncooperative = sorted(schedule_uncooperative, key=lambda task: task.arrival_time)
            schedule_uncooperative_left = copy.copy(schedule_uncooperative)

            # try to feet the remain tasks
            for un_task in schedule_uncooperative:
                if legal_schedule_cooperative: e_co_task = legal_schedule_cooperative[0]
                for co_task in legal_schedule_cooperative:
                    if co_task == e_co_task:
                        distant_time = co_task.arrival_time - self.free_start_time
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
                                self.free_start_time + un_task.travel_from())
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
                    task.update_startTime(self.free_start_time + task.travel_from())
                else:
                    task.update_startTime(e_task.leaving_time + task.travel_from(e_task))
                e_task = task
            if self.updated_heuristic: # if updated heuristic earliestTimes of the overlap_task
                for task in overlap_task :
                    self.earliestTimes[task.requester][task.skill] = task.arrival_time

            self.final_schedule = sorted(legal_schedule_cooperative + schedule_uncooperative_left,
                                         key=lambda task: task.arrival_time)

    def compute_R(self):  # R חישוב ה
        #  complete offers
        if self.type == 'HSM':
            for sr in self.srs.keys():
                for skill in self.srs[sr]['skills'].keys():
                    offer = self.srs[sr]['offers'][skill]
                    offer.provider = self
                    offer.arrival_time = self.free_start_time + self.travel_time(self.location, offer.location)
                    offer.amount = self.skill_set[skill]
                    offer.leaving_time = self.free_start_time + 999999
                    offer.accept = True
                    if sr not in self.offers: self.offers[sr] = {}
                    self.offers[sr][skill] = offer


        # compute_R
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


            # normalize R
            for sr in self.R.keys():
                for skill in self.R[sr].keys():
                    if Rs[skill] != 0:
                        self.R[sr][skill] = self.R[sr][skill] / Rs[skill]

    ########################################### sub function
    def reset_view(self):
        if self.type != "commit" and self.temporary_first :
            self.committed_final_schedule.append(self.temporary_first[0])
            self.skill_set[self.temporary_first[0].skill] -=self.temporary_first[0].allocation
            self.temporary_first.pop(0)
        self.allocations = {}
        self.allocations_cap = {}
        self.old_schedule = copy.copy(self.schedule)
        self.schedule = []
        if self.final_schedule and not self.temporary_first:
            self.first = self.final_schedule[0]
        else:
            self.first = None
        self.commits = {}
        self.arrival_time = {}
        self.depth += 1



    def filter_skills(self, skills):
        new_skills = {}
        for skill in skills.keys():
            if skill in self.skills:
                new_skills[skill] = skills[skill]
        return new_skills

    def get_schedule(self):
        return self.committed_final_schedule + self.final_schedule

    def commit(self, first):
        print(f' sp {self._id} commit to sr {first.requester} | skill {first.skill}')
        self.temporary_first.append(first)
        self.offers[first.requester].pop(first.skill)
        if not self.offers[first.requester]: self.offers.pop(first.requester)


        self.location = first.location
        self.free_start_time = first.leaving_time

        self.type = 'commit'

        for sp in self.offers:
            for skill in self.offers[sp]:
                offer = self.offers[sp][skill]
                offer.arrival_time = self.free_start_time + self.travel_time(self.location, offer.location)
                offer.amount = self.skill_set[skill]


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

    def compute_NCLO(self):
        in_ = max(len(self.allocations),len(self.arrival_time),len(self.commits))
        out_ = max(len(self.bids),len(self.earliestTimes))
        self.NCLO += super().number_of_comparisons(out_, in_)











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