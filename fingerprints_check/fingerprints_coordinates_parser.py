import os
import csv
import shutil
import mlrose
from math import sqrt
from os import listdir
from os.path import isfile, join


def main():

    input_folder = "xy_folder"
    out_folder = input_folder + "_weight_center"
    out_matrix_folder = input_folder + "_coordinates_matrix"
    out_fitness_folder = input_folder + "_fitness"

    # recreate folders
    directories = (out_folder, out_fitness_folder, out_matrix_folder)
    for dir_ in directories:
        if os.path.exists(dir_):
            shutil.rmtree(dir_)
        os.mkdir(dir_)

    # create list of all file names in directory
    only_files = [f for f in listdir(input_folder) if isfile(join(input_folder, f))]
    all_fitness_list = []
    for in_file in only_files:
        temp_list = []
        segments_list = []
        with open(f"{input_folder}/{in_file}") as tsv:
            file_len = 0
            sum_x = 0
            sum_y = 0
            for line in csv.reader(tsv, dialect="excel-tab"):
                # calculate summary of each type of coordinates
                x = int(line[1])
                y = int(line[2])
                sum_x += x
                sum_y += y
                temp_list.append((x, y))
                file_len += 1
        print("file_len ", file_len)
        # create file with weight_center of each type coordinates
        x_weight_center = sum_x / file_len
        y_weight_center = sum_y / file_len
        with open(f"{out_folder}/{in_file}", "w") as o_f:
            o_f.write(f"{str(x_weight_center)}\t{str(y_weight_center)}")
        # create matrix and write it to file
        with open(f"{out_matrix_folder}/{in_file}", "a+") as m_f:
            for x in range(0, 504):
                for y in range(0, 480):
                    for z in temp_list:
                        if x == z[0] and y == z[1]:
                            # m_f.write('1')
                            sigment_distance = round(
                                sqrt(
                                    pow((x - x_weight_center), 2)
                                    + pow((y - y_weight_center), 2)
                                ),
                                2,
                            )
                            segments_list.append([x, y, sigment_distance])
                            break
                    # m_f.write('0')
                # m_f.write('\n')
        segments_list.sort(key=lambda x: x[2])
        segment_list_cutted = segments_list[:36]
        print(segment_list_cutted)
        out_fitness_list = []
        for x in range(0, len(segment_list_cutted), 6):
            print(segment_list_cutted[x : x + 6])
            coords_list = [[x[0], x[1]] for x in segment_list_cutted[x : x + 6]]
            # Initialize fitness function object using coords_list
            fitness_coords = mlrose.TravellingSales(coords=coords_list)
            problem_fit = mlrose.TSPOpt(
                length=len(coords_list), fitness_fn=fitness_coords, maximize=False
            )
            # Solve problem using the genetic algorithm
            best_state, best_fitness = mlrose.genetic_alg(
                problem_fit, mutation_prob=0.2, max_attempts=100, random_state=2
            )
            best_fitness = round(best_fitness, 2)
            print("The best state found is: ", best_state)
            print("The fitness at the best state is: ", best_fitness)
            out_fitness_list.append(best_fitness)
        out_fitness_list.sort()
        all_fitness_list.append(out_fitness_list)

    # write results to the file
    with open(f"{out_fitness_folder}/fitness.csv", "w") as csvFile:
        ff = csv.writer(csvFile)
        for obj in zip(*all_fitness_list):
            ff.writerow(obj)


if __name__ == '__main__':
    main()
