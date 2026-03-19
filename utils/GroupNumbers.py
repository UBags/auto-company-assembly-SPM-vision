import sys
import os

def compute_median(data, start, end):
    length = end - start + 1
    mid_idx = start + length // 2
    if length % 2 == 1:
        return data[mid_idx]
    else:
        return (data[mid_idx - 1] + data[mid_idx]) / 2.0


def is_valid_group(data, start, end, max_allowed_deviation):
    if start > end:
        return False
    m = compute_median(data, start, end)
    if m <= 0:  # Safety for zero/negative (adjust if your data can include them)
        return all(x == m for x in data[start:end + 1])
    lower = m * (1 - max_allowed_deviation)
    upper = m * (1 + max_allowed_deviation)
    return (data[start] >= lower - 1e-9) and (data[end] <= upper + 1e-9)


def group_left_to_right(data, max_allowed_deviation):
    n = len(data)
    groups = []
    medians = []
    i = 0
    while i < n:
        end = i
        j = i + 1
        while j <= n:
            if is_valid_group(data, i, j - 1, max_allowed_deviation):
                end = j - 1
                j += 1
            else:
                break
        group = data[i:end + 1]
        groups.append(group)
        medians.append(compute_median(data, i, end))
        i = end + 1
    return groups, medians


def group_right_to_left(data, max_allowed_deviation):
    n = len(data)
    groups = []
    medians = []
    pos = n
    while pos > 0:
        end = pos - 1
        start = end
        while start > 0 and is_valid_group(data, start - 1, end, max_allowed_deviation):
            start -= 1
        group = data[start:end + 1]
        groups.append(group)
        medians.append(compute_median(data, start, end))
        pos = start
    groups.reverse()
    medians.reverse()
    return groups, medians


def separation_score(medians):
    if len(medians) < 2:
        return (float('inf'), float('inf'))
    diffs = [medians[i + 1] - medians[i] for i in range(len(medians) - 1)]
    return (min(diffs), sum(diffs))


def group_numbers(numbers, max_allowed_deviation):
    data = sorted(numbers)
    if not data:
        return [], []

    # Run both directions
    groups_l, medians_l = group_left_to_right(data, max_allowed_deviation)
    groups_r, medians_r = group_right_to_left(data, max_allowed_deviation)

    # Choose the better one for separation
    score_l = separation_score(medians_l)
    score_r = separation_score(medians_r)

    if score_l >= score_r:
        return groups_l, medians_l
    else:
        return groups_r, medians_r


# Example usage
# if __name__ == "__main__":
#     numbers = [9.5, 13.5, 15.5, 16, 16.7, 17.5, 19, 22, 23, 24, 24.5, 25, 27]
#     max_allowed_deviation = 0.2
#
#     groups, medians = group_numbers(numbers, max_allowed_deviation)
#     print("Groups:", groups)
#     print("Medians:", medians)
#     print("Consecutive differences:", [medians[i + 1] - medians[i] for i in range(len(medians) - 1)])