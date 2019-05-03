#!env/bin/python3

from abots.helpers import jsto
from abots.events import ThreadPoolManager

from urllib.request import urlopen
from threading import Event
from time import monotonic, sleep

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
    print("Gathering new stories")
    hn_new_stories = "https://hacker-news.firebaseio.com/v0/topstories.json"
    items = jsto(urlread(hn_new_stories))
    # stories = dict()
    print(f"Gathered {len(items)} stories")
    for i, item in enumerate(items):
        # print(f"[{i}] Processing story '{item}'")
        get_hn_story(item, score_threshold)
    elapsed = monotonic() - hn_start
    print("Done processing")
    return elapsed

def gen_hn_threaded(score_threshold, manager):
    hn_start = monotonic()
    print("Gathering new stories")
    hn_new_stories = "https://hacker-news.firebaseio.com/v0/topstories.json"
    items = jsto(urlread(hn_new_stories))
    tasks = list()
    print(f"Gathered {len(items)} stories")
    for i, item in enumerate(items):
        # print(f"[{i}] Processing story '{item}'")
        task = manager.reserve(get_hn_story, (item, score_threshold))
        tasks.append(task)
    for task in tasks:
        task.wait()
    elapsed = monotonic() - hn_start
    print("Done processing")
    return elapsed

print("Loading manager")
pool_size = 12
test_size = pool_size * 3
pre_start = monotonic()
manager = ThreadPoolManager(pool_size)
loading = monotonic() - pre_start
print(f"Loading: {loading:0.2f}s")

score_threshold = 300
print("Starting normal")
normal_time = gen_hn(score_threshold)
print(f"Normal: {normal_time:0.2f}s")
print("Starting threaded")
threaded_time = gen_hn_threaded(score_threshold, manager)
print(f"Threaded: {threaded_time:0.2f}s")

print("Stopping manager")
post_start = monotonic()
manager.stop()
manager.stopped.wait()
stopping = monotonic() - post_start
print(f"Stopping: {stopping:0.2f}s")

result_time = loading + threaded_time + stopping
print(f"\n[RESULTS] Normal: {normal_time:0.2f}s\tThreaded: {result_time:0.2f}s")