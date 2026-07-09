# Presentation script (English, per slide, 12-15 min)

The talk is in English (slides.pdf, 15 slides). Split evenly: 5 slides each, and
each person presents their own language and the part they built. The live demo is
at the end, done by all three.

## Overall split (5 slides each)

| Person | Language | Slides | Their part |
|---|---|---|---|
| Melissa | Java | 1, 2, 5, 12, 15 | Intro, architecture, Watcher desktop (Java), closing |
| Junior | Go | 3, 6, 7, 9, 10 | Constraints, Raft, protocol, cluster, failover (Go node) |
| Andrew | Python | 4, 8, 11, 13, 14 | Team, CNN, recognition, mobile, wrap-up (Python node) |

Each person speaks ~4 minutes.

---

## Slide 1 — Title (Melissa, 20 s)
"Hi, we are Melissa, Junior and Andrew. Our final project is a distributed
object-recognition system that uses an AI model and the Raft consensus algorithm.
Each of us built one node in a different language."

## Slide 2 — The problem (Melissa, 1 min)
"The goal is to recognize objects, animals or people with a trained AI model, and
to keep the whole detection log consistent and fault-tolerant using Raft. The
system has four parts: a training server, a testing server with the cameras, a
watcher client, and the Raft consensus module."
-> Melissa hands over to Junior.

## Slide 3 — Hard constraints (Junior, 1 min)
"The assignment had strict rules: raw native sockets only, no WebSocket, no MQ, no
frameworks, so we implemented Raft by hand over TCP. Three languages, one per
member. Two operating systems. Threads. Local deployment, no internet. And only the
base libraries of each language, with NumPy allowed for the neural network."
-> Junior hands over to Andrew.

## Slide 4 — Team and languages (Andrew, 40 s)
"Each of us owns a language: Melissa did Java, with the Raft core, the training and
the desktop interface. Junior did Go, with his Raft node and the record state
machine. I did Python, with the CNN and the testing server. The key point: all
three nodes speak the same text protocol, so they form a single cluster even though
they are different languages."
-> Andrew hands over to Melissa.

## Slide 5 — System architecture (Melissa, 1.5 min)
"This is the flow: the cameras feed the testing server, which runs the CNN. Each
detection is sent to the leader of the Raft cluster, which replicates it across the
three nodes. The watcher client reads that replicated log. Every write goes through
the leader and is committed once the majority has copied it."
-> Melissa hands over to Junior.

## Slide 6 — Raft: leader election and log replication (Junior, 2 min)
"I built the Go node and the consensus logic, so let me explain Raft. Raft is how
several machines agree even if one fails. There are three states: follower,
candidate and leader. A leader is elected using a random timeout between 150 and
300 milliseconds to avoid ties. The leader takes each detection, puts it in its log
and replicates it; an entry is committed only when it is on the majority. If the
leader dies, the others elect a new one. We implemented all of this by hand,
following the Raft paper from class."

## Slide 7 — The text protocol (Junior, 1.5 min)
"Everything runs over this text protocol, one message per line with fields split by
a pipe. RequestVote and AppendEntries for the consensus; NUEVA_DETECCION to insert
a detection; LEER_REGISTRO for the watcher to read. Because Java, Python and Go all
use exactly this format, a Python leader can replicate to a Java or Go follower with
no translation layer. My Go node interoperates with the other two directly."
-> Junior hands over to Andrew.

## Slide 8 — The CNN (Andrew, 2.5 min)
"I built the AI part in Python. It is a convolutional neural network written from
scratch with NumPy, no TensorFlow or PyTorch. It recognizes 10 real classes from
CIFAR-10: airplane, car, cat, dog, boat, truck, and so on. Two convolutional
layers, pooling, and a dense layer with softmax, with forward and backward
propagation by hand. We train it beforehand and save the weights, so it runs
offline. It gets 40.9% on the test set, four times better than random for a small
from-scratch network on real objects. The training is also distributed across
several processes in parallel."
-> Andrew hands over to start the demo.

## Slides 9-13 — LIVE DEMO (all three run their node, ~4 min)

Here we run the real demo. Each of us runs our own node, so the three languages are
visible.

**Slide 9 (End-to-end) — Junior talks:** while the nodes come up.
"Each of us starts our node." (the three run their command from GUION-DEMO.md:
Melissa the Java node, Andrew the Python node, Junior the Go node.) "A leader has
been elected, and the three nodes apply the same detections in the same order."

**Slide 10 (Fault tolerance) — Junior talks, the star moment:** "Now we kill the
leader node..." (whoever is the leader presses Ctrl+C). "...and look: another node
is elected leader and the log stays intact. That is the fault tolerance of Raft
consensus, working across three separate machines."

**Slide 11 (Recognition) — Andrew talks:** "The camera recognizes the objects live,
and each detection is inserted into the cluster." (show the camera window with
"Detecto: X"). A phone acts as an IP camera here.

**Slide 12 (Watcher desktop) — Melissa talks:** "Each detection shows up here in the
watcher, with its photo, type, camera and time." (show the desktop Watcher).

**Slide 13 (Mobile) — Andrew talks:** "And the same log is visible from the native
Android app." (show the phone or emulator).

## Slide 14 — Wrap-up (Andrew, 30 s)
"To sum up, we met the three parts: recognition with a trained AI, fault-tolerant
Raft consensus, and three languages interoperating with raw native sockets only."
-> Andrew hands over to Melissa.

## Slide 15 — Thank you (Melissa, 15 s)
"Thank you, we are happy to take questions."

---

## Rules so it goes well

- **Rehearse the demo once.** Everyone should know their command by heart
  (see docs/GUION-DEMO.md).
- **Each person runs their own node** in the demo, so the three languages are shown.
  Melissa also runs the camera, video server and watcher.
- If the demo fails live: use the safe mode (`camara_demo.py`) or run the three
  nodes on one laptop with `127.0.0.1`. Never freeze: the slides are the backup.
- **Timing:** if short on time, the demo shrinks to: start nodes -> show watcher with
  detections -> kill leader. That is what the professor grades the most.

## Likely questions and how to answer (in English)

- "Why only 40.9%?" -> "It is a small CNN written by hand in NumPy on CIFAR-10, no
  frameworks and no pre-training. 40.9% is honest; random is 10%."
- "How do I know you didn't use frameworks?" -> show the raw socket code and the
  text protocol.
- "What if two nodes go down?" -> "With 3 nodes, Raft tolerates 1 failure (majority
  of 2). With 5 nodes it would tolerate 2. It is configurable."
- "Does it run on two operating systems?" -> "Yes, the nodes listen on 0.0.0.0; in
  the demo they run on Mac and Windows/Linux."
- "Are the cameras real?" -> "Yes, a phone acts as an IP camera streaming over WiFi;
  the laptop reads the stream and the CNN recognizes it."
