import os

import pandas as pd
import matplotlib.pyplot as plt


if __name__ == "__main__":

    for sp in range(35, 45, 5):
        for sr in range(10, 25, 5):
            for simulation in ["CTTD", "Abstract"]:
                file_path = os.path.join('Results', 'python_simulation_outputsUtility_20_problems_%s_SPs_%s_SRs_%s'
                                                    '_simulator.xlsx'%(sp, sr, simulation))
                try:
                    df = pd.read_excel(file_path, sheet_name='Global Utility Over NCLO %s'  % simulation)
                    print ('success: %s' % str(file_path))
                    title = str(
                        "%s SPs %s SRs %s simulator" % (sp, sr, simulation))

                    #plot
                    line_style = {'1': 'solid', '2': 'dashed', '3': 'dotted'}
                    colors = {'0':'red', '1':'blue', '3':'green', '4':'purple', '5':'orange'}
                    columns = df.columns[1:]
                    for column in columns:
                        plt.plot(df.iloc[:, 0], df[column], color=colors[column[4]], linewidth=2,
                                 linestyle= line_style[column[-1]])

                    plt.xlabel('NCLO')
                    plt.ylabel('Utility')
                    plt.title(title)  # Add a header to the chart
                    # set up legend
                    plt.plot([], [], label='RPA Versions:', linestyle='None', color='orange', linewidth=2)
                    plt.plot([], [], label='RPA', linestyle='solid', color='red', linewidth=2)
                    plt.plot([], [], label='RPA_SA', linestyle='solid', color='blue', linewidth=2)
                    plt.plot([], [], label='RPA_I', linestyle='solid', color='green', linewidth=2)
                    plt.plot([], [], label='RPA_FS', linestyle='solid', color='purple', linewidth=2)
                    plt.plot([], [], label='RPA_FSOS', linestyle='solid', color='orange', linewidth=2)
                    plt.plot([], [], label='Bid Versions:', linestyle='None', color='orange', linewidth=2)
                    plt.plot([], [], label='Coverage', linestyle='solid', color='black', linewidth=2)
                    plt.plot([], [], label='Based_Shapley',  linestyle='dashed', color='black', linewidth=2)
                    plt.plot([], [], label='Simple',  linestyle='dotted', color='black', linewidth=2)
                    plt.legend()
                    plt.savefig(title +'.png')
                    plt.clf()
                except Exception:
                    pass
                    # print('File Not Found: %s' % file_path)