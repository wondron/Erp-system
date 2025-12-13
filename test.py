
import os



with open("aaa.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(len(lines))


for line in lines:
    newdd = line.replace('\n', '')
    print(newdd.split('\\')[-1])