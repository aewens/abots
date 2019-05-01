#!env/bin/python3

from abots.helpers import jsto
from abots.events import ThreadPoolManager

from urllib.request import urlopen
from time import monotonic

def urlread(url):
    with urlopen(url) as u:
        return u.read().decode("utf-8")

def get_hn_story(item, score_threshold):
    story_url = f"https://hacker-news.firebaseio.com/v0/item/{item}.json"
    hn_story = jsto(urlread(story_url))
    score = hn_story.get("score", 0)
    if score >= score_threshold:
        return item, hn_story
    # return None

def gen_hn(score_threshold):
    hn_start = monotonic()
    # print("Gathering new stories")
    hn_new_stories = "https://hacker-news.firebaseio.com/v0/topstories.json"
    items = jsto(urlread(hn_new_stories))
    # stories = dict()
    for i, item in enumerate(items):
        # print(f"[{i}] Processing story '{item}'")
        get_hn_story(item, score_threshold)
    elapsed = monotonic() - hn_start
    # print("Done processing")
    return elapsed

def gen_hn_threaded(score_threshold):
    hn_start = monotonic()
    # print("Gathering new stories")
    hn_new_stories = "https://hacker-news.firebaseio.com/v0/topstories.json"
    items = jsto(urlread(hn_new_stories))
    # stories = dict()
    for i, item in enumerate(items):
        # print(f"[{i}] Processing story '{item}'")
        Thread(target=get_hn_story, args=(item, score_threshold)).start()
    elapsed = monotonic() - hn_start
    # print("Done processing")
    return elapsed

# score_threshold = 300
# print("Starting normal")
# elapsed1 = gen_hn(score_threshold)
# print("Starting threaded")
# elapsed2 = gen_hn_threaded(score_threshold)
# print(f"First: {elapsed1:0.2f}s\tSecond: {elapsed2:0.2f}s")

# Awful on purpose
def fib(n):
    if n <= 1:
        return 1
    return fib(n - 1) + fib(n - 2)

def normal(n, size):
    fib_start = monotonic()
    for s in range(size):
        fib(n)
    elapsed = monotonic() - fib_start
    return elapsed

def threaded(n, size, manager):
    fib_start = monotonic()
    tasks = list()
    while len(tasks) < size:
        args = (n,)
        task = manager.reserve(fib, args)
        tasks.append(task)
    for task in tasks:
        task.wait()
    elapsed = monotonic() - fib_start
    return elapsed

print("Loading manager")
test_size = 24
pool_size = int(test_size / 2)
pre_start = monotonic()
manager = ThreadPoolManager(pool_size)
loading = monotonic() - pre_start
print(f"Loading: {loading:0.2f}s")

n = 25
print("Starting normal")
normal_time = normal(n, test_size)
print("Starting threaded")
threaded_time = threaded(n, test_size, manager)
print(f"Normal: {normal_time:0.2f}s\tThreaded: {threaded_time:0.2f}s")

print("Stopping manager")
post_start = monotonic()
manager.stop()
manager.stopped.wait()
stopping = monotonic() - post_start
print(f"Stopping: {stopping:0.2f}s")

result_time = loading + threaded_time + stopping
print(f"\n[RESULTS] Normal: {normal_time:0.2f}s\tThreaded: {result_time:0.2f}s")