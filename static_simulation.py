import copy
import math
import os
import openpyxl as openpyxl
import pandas as pd
import matplotlib.pyplot as plt
from Simulator.AbstractSimulator.AbstractSimulatorComponents import AbstractSimulatorCreator
from Simulator.CTTD.CttdSimulatorComponents import CttdSimulatorComponents
from Solver.SolverAbstract import Mailer, Agent
from SynchronizedAlgorithms.RPA.Main_RPA import RPA
from SynchronizedAlgorithms.DSRM.Main_DSRM import DSRM
from SynchronizedAlgorithms.FMC_TA.Main_FMC_TA import FMC_TA

dbug = True
alfa = 0.7  # RPA dumping prop
SR_amount = [20]
SP_amount = [21]
problems_amount = 41
algorithm_type =['FMC TA_',"FMC TA repetitive_","FMC TA repetitive updated heuristic_","DSRM", "RPA"]  # ["DSRM", "RPA", FMC_TA]
# algorithm_type =['FMC TA_',"FMC TA repetitive","FMC TA repetitive updated heuristic_"]  # ["DSRM", "RPA", FMC_TA]
solver_type = ["SOMAOP"]  # 1-SOMAOP 2-DCOP
simulation_type = ["Abstract"]  # "Abstract", "CTTD"
algorithm_version = [1,3]  # [0, 1, 2, 3, 4, 5] 0: regular version, 1: SA, 3: incremental  4: full schedule, 5: full schedule one shote 2 - dumping not in use
bid_type = [1]  # [1, 2, 3] 1 - coverage bid/ truncated, 2 - shapley, 3- simple
termination = 250  # termination for RPA

# for DCOP privacy coherency
assignmentPrivacy = [0.0, 0.25, 0.5, 0.75, 1]
constraintPrivacy = [0.0, 0.25, 0.5, 0.75, 1]

########## fmc+
min_work_split = 0.0001
e = 0.001
max_termination_fmc = 5000
########## fmc+

# create simulation problems
def create_problems_simulation():
    ans = []
    for i in range(0, problems_amount):
        problem = create_new_problem(i)
        ans.append(problem)
    return ans


def create_new_problem(problem_id):
    if simulation == "Abstract":
        new_prob = AbstractSimulatorCreator(number_of_providers=SP, number_of_requesters=SR, prob_id=problem_id)
    elif simulation == "CTTD":
        new_prob = CttdSimulatorComponents(number_of_providers=SP, number_of_requesters=SR, prob_id=problem_id)
    return new_prob


# create solver for each problem and solve
def solve_problems(in_problems):
    for problem in in_problems:
        solver = create_synchronized_solver(problem)  # todo
        create_and_meet_mailer(solver.agents, problem.problem_id, solver)
        solver.execute_algorithm()
        print("solve problem %s" % problem.problem_id)
        update_problem_utility_new_version(solver.total_util_over_NCLO)


def create_synchronized_solver(problem):
    if p_type == "SOMAOP":
        if algorithm.split("_")[0] == "RPA":
            return RPA(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                       max_iteration=termination, bid_type=bid, algorithm_version=version, alfa=alfa)
        if algorithm.split("_")[0] == "DSRM":
            return DSRM(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                        bid_type=bid, algorithm_version=version)

########## fmc+
        # "FMC TA_","FMC TA repetitive_","FMC TA repetitive_"
        print(algorithm.split("_")[0])
        if algorithm.split("_")[0] == "FMC TA":
            fmc = FMC_TA(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                         max_iteration=termination, bid_type=bid, algorithm_version=4,
                         min_work_split=min_work_split,
                         e=e)
            return fmc
        if algorithm.split("_")[0] == "FMC TA repetitive":
            fmc = FMC_TA(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                         max_iteration=max_termination_fmc, bid_type=bid, algorithm_version=2,
                         min_work_split=min_work_split,
                         e=e)
            return fmc
        if algorithm.split("_")[0] == "FMC TA repetitive updated heuristic" :
            fmc = FMC_TA(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                         max_iteration=max_termination_fmc, bid_type=bid, algorithm_version=0,
                         min_work_split=min_work_split,
                         e=e)
            return fmc
        if algorithm.split("_")[0] == "FMC TA updated heuristic" :
            fmc = FMC_TA(problem_id=problem.problem_id, providers=problem.providers, requesters=problem.requesters,
                         max_iteration=max_termination_fmc, bid_type=bid, algorithm_version=1,
                         min_work_split=min_work_split,
                         e=e)
            return fmc

########## fmc+

def create_and_meet_mailer(agents: [Agent], problem_id, solver):
    mailer = Mailer(problem_id=problem_id, agents=agents)
    for a in agents: a.meet_mailer(mailer)
    solver.meat_mailer(mailer)
    return mailer


# export data to excel
def to_excel():
    string_name = str("Utility_%s_problems_%s_SPs_%s_SRs_%s_simulator" % (problems_amount, SP, SR, simulation))
    path = 'C:\\Users\ת\\Desktop\\לימודים _4_ב\\פרוייקט ב\\תוצאות'

    writer = pd.ExcelWriter(path + string_name + '.xlsx', engine='openpyxl')

    sheet_run_info = 'Run Information ' + simulation
    sheet_global_utility = 'Global Utility Over NCLO ' + simulation
    runInformation.to_excel(writer, sheet_name=sheet_run_info)
    # update_global_util_for_all_NCLOs()
    update_global_util_for_all_NCLOs_new_ver()
    globalUtilityOverNCLODF = pd.DataFrame.from_dict(data=global_utility_over_NCLO)
    globalNCLOsDF = pd.DataFrame(data=sorted(globalNCLOs), columns=['NCLO'])
    globalNCLOsDF.to_excel(writer, sheet_name=sheet_global_utility, startcol=0, index=False)
    globalUtilityOverNCLODF.to_excel(writer, sheet_name=sheet_global_utility, startcol=1, index=False)

    writer._save()


def plot_chart():
    string_name = str("Utility_%s_problems_%s_SPs_%s_SRs_%s_simulator" % (problems_amount, SP, SR, simulation))
    for algo in global_utility_over_NCLO:
        x = sorted(global_utility_over_NCLO[algo].keys())
        y = [global_utility_over_NCLO[algo].get(i, None) for i in x]
        plt.plot(x, y, label=algo)

    plt.xlabel('NCLO')
    plt.ylabel('Utility')
    plt.title(string_name)  # Add a header to the chart
    plt.legend()
    plt.show()


# init data frame for output
def initiate_df():
    columns = ['number_of_problems', 'number_of_providers', 'number_of_requesters', 'simulation_type']
    runInformation = pd.DataFrame(columns=columns)
    runInformation = runInformation._append(pd.DataFrame([[problems_amount, SP, SR, simulation]]
                                                         , columns=columns), ignore_index=True)
    return runInformation


# add algorithm dict to df
def initiate_data_frames_fo_algorithm():
    global_utility_over_NCLO[algorithm] = {}


def update_problem_utility_new_version(problem_utility_over_NCLO):
    NCLOs = list(problem_utility_over_NCLO.keys())
    last_value = 0
    last_global_nclo_update = copy.deepcopy(global_utility_over_NCLO[algorithm])
    # if this is the first experiment
    if len(global_utility_over_NCLO[algorithm]) == 0:
        global_utility_over_NCLO[algorithm] = copy.deepcopy(problem_utility_over_NCLO)
        globalNCLOs.update(NCLOs)
    else:
        remaining_new_NCLOs = NCLOs
        remaining_existing_NCLOs = list(global_utility_over_NCLO[algorithm].keys())
        globalNCLOs.update(remaining_new_NCLOs + remaining_existing_NCLOs)
        for nclo in NCLOs:
            if nclo in last_global_nclo_update:
                remaining_existing_NCLOs.remove(nclo)
                new_utility = (last_global_nclo_update[nclo] + problem_utility_over_NCLO[nclo]) / 2
                global_utility_over_NCLO[algorithm][nclo] = new_utility
            else:
                if not remaining_existing_NCLOs :remaining_existing_NCLOs.append(0)
                last_nclo = min(min(remaining_new_NCLOs), min(remaining_existing_NCLOs))

                for i in last_global_nclo_update.keys():
                    if last_nclo < i < nclo:
                        last_nclo = i

                new_utility = problem_utility_over_NCLO[nclo] + 0
                if last_nclo in last_global_nclo_update.keys():
                    new_utility = (last_global_nclo_update[last_nclo] + problem_utility_over_NCLO[nclo]) / 2
                global_utility_over_NCLO[algorithm][nclo] = new_utility

            # update interval
            for i in last_global_nclo_update.keys():
                if nclo > i > last_value:
                    new_utility = (last_global_nclo_update[i] + problem_utility_over_NCLO[nclo]) / 2
                    global_utility_over_NCLO[algorithm][i] = new_utility

            last_value = nclo

        # add last value to dict
        for i in last_global_nclo_update.keys():
            if i > last_value:
                new_utility = (last_global_nclo_update[i] + problem_utility_over_NCLO[last_value]) / 2
                global_utility_over_NCLO[algorithm][i] = new_utility


# add global utility solver
def update_problem_utility_over_NCLO(problem_utility_over_NCLO):
    NCLOs = list(problem_utility_over_NCLO.keys())
    # if this is the first experiment
    if len(global_utility_over_NCLO[algorithm]) == 0:
        global_utility_over_NCLO[algorithm] = copy.deepcopy(problem_utility_over_NCLO)
        globalNCLOs.update(NCLOs)
    else:  # merge NCLO utility average
        outcome_dict = {}
        remaining_new_NCLOs = NCLOs
        remaining_existing_NCLOs = list(global_utility_over_NCLO[algorithm].keys())
        globalNCLOs.update(remaining_new_NCLOs + remaining_existing_NCLOs)
        current_saved_new_utility = 0
        current_saved_existing_utility = 0
        current_saved_total_utility = 0
        while remaining_new_NCLOs or remaining_existing_NCLOs:
            if remaining_new_NCLOs:
                new_NCLO = min(remaining_new_NCLOs)
            else:
                new_NCLO = math.inf
            if remaining_existing_NCLOs:
                existing_NCLO = min(remaining_existing_NCLOs)
            else:
                existing_NCLO = math.inf

            if new_NCLO < existing_NCLO:  # need to add whats in the new
                diff = problem_utility_over_NCLO[new_NCLO] - current_saved_new_utility
                current_saved_total_utility += diff
                current_saved_new_utility += diff
                outcome_dict[new_NCLO] = current_saved_total_utility
                remaining_new_NCLOs.remove(new_NCLO)
            elif existing_NCLO < new_NCLO:
                diff = global_utility_over_NCLO[algorithm][existing_NCLO] - current_saved_existing_utility
                current_saved_total_utility += diff
                current_saved_existing_utility += diff
                outcome_dict[existing_NCLO] = current_saved_total_utility
                remaining_existing_NCLOs.remove(existing_NCLO)
            else:
                diff1 = global_utility_over_NCLO[algorithm][existing_NCLO] - current_saved_existing_utility
                current_saved_existing_utility += diff1
                diff2 = problem_utility_over_NCLO[new_NCLO] - current_saved_new_utility
                current_saved_new_utility += diff2
                current_saved_total_utility += diff1 + diff2
                outcome_dict[new_NCLO] = current_saved_total_utility
                remaining_new_NCLOs.remove(new_NCLO)
                remaining_existing_NCLOs.remove(existing_NCLO)

        global_utility_over_NCLO[algorithm] = outcome_dict


# update the global utility for df
def update_global_util_for_all_NCLOs_new_ver():
    for algo in global_utility_over_NCLO:
        all_NCLOs_list = sorted(list(globalNCLOs))
        new_dict = {}
        last_utility = 0.0
        global_utility_over_NCLO_sorted = dict(sorted(global_utility_over_NCLO[algo].items()))
        for NCLO, utility in global_utility_over_NCLO_sorted.items():
            utility = float(utility)
            for next_NCLO in copy.copy(all_NCLOs_list):
                if next_NCLO < NCLO:
                    new_dict[next_NCLO] = max(last_utility, utility)  # todo edit if needed
                    all_NCLOs_list.remove(next_NCLO)
                elif next_NCLO == NCLO:
                    new_dict[next_NCLO] = utility  # / problems_amount
                else:
                    break
            last_utility = utility  # / problems_amount

        for next_NCLO in copy.copy(all_NCLOs_list):
            new_dict[next_NCLO] = last_utility

        global_utility_over_NCLO[algo] = new_dict


def update_final_utility_over_agents_amount():
    '''
    this method update the final utility for each problem size
    '''
    if algorithm in global_utility_over_NCLO.keys():
        last_utility = global_utility_over_NCLO[algorithm][
            max(global_utility_over_NCLO[algorithm].keys())]  # the last utility
        problem_size = ('SR%sSP%s' % (SR_amount, SP_amount))
        if algorithm not in final_utility_over_agents_amount.keys():
            final_utility_over_agents_amount[algorithm] = {}
        else:
            final_utility_over_agents_amount[algorithm][problem_size] = last_utility


def update_global_util_for_all_NCLOs():
    for algo in global_utility_over_NCLO:
        all_NCLOs_list = sorted(list(globalNCLOs))

        new_dict = {}
        last_utility = 0.0

        for NCLO, utility in global_utility_over_NCLO[algo].items():
            utility = float(utility)
            for next_NCLO in copy.copy(all_NCLOs_list):
                if next_NCLO < NCLO:
                    new_dict[next_NCLO] = last_utility
                    all_NCLOs_list.remove(next_NCLO)
                elif next_NCLO == NCLO:
                    new_dict[next_NCLO] = utility
                else:
                    break
            last_utility = utility

        for next_NCLO in copy.copy(all_NCLOs_list):
            new_dict[next_NCLO] = last_utility

        global_utility_over_NCLO[algo] = new_dict


# main run simulation
if __name__ == '__main__':
    for simulation in simulation_type:
        for SR in SR_amount:
            final_utility_over_agents_amount = {}  # {problems size: utility}
            for SP in SP_amount:
                if SP > SR:
                    # output variables
                    global_utility_over_NCLO = {}
                    globalNCLOs = set()
                    for p_type in solver_type:
                        runInformation = initiate_df()
                        for algorithm in algorithm_type:
                            for version in algorithm_version:
                                for bid in bid_type:
                                    algorithm = algorithm.split('_')[0] + '_' + str(version) + '_' + str(bid)
                                    if algorithm.startswith('DSRM') and version != 1:
                                        continue
                                    if algorithm.startswith('FMC') and version != 1:
                                        continue
                                    initiate_data_frames_fo_algorithm()
                                    if dbug:
                                        print("Running simulation. \n %s SPs, %s SRs problem type: "
                                              "%s \n algorithm %s bid type: %s"
                                              % (SP, SR, p_type, algorithm, bid))
                                    problems = create_problems_simulation()
                                    solve_problems(in_problems=problems)
                            to_excel()
                        plot_chart()
                    update_final_utility_over_agents_amount()
