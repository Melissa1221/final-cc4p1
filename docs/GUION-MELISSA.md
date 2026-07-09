# Guion de Melissa — Slides 3, 4, 5, 6 (English)

Lo que decir en cada una de tus diapositivas, palabra por palabra. En ingles.
Tono tecnico. Total: ~5 min.

---

## SLIDE 3 — Hard constraints from the assignment (~1 min)

"These are the hard constraints the assignment gave us, and they shaped every
design decision.

First, raw native sockets only — no WebSocket, no Socket.IO, no RabbitMQ, no
communication frameworks. This is the strictest one: it means we implemented Raft
by hand, directly over TCP.

Second, three programming languages, one node per student: Java, Python and Go.

Third, it must run on two different operating systems using the same set of
languages.

We also had to use threads — for performance and to avoid corrupting the shared
record.

Everything runs locally, without internet, over LAN and WiFi.

And we could only use each language's base libraries — the one exception is NumPy,
allowed for the neural network."

> Si preguntan por que prohibe frameworks:
> "To prove we actually understand the low-level networking and the consensus
> algorithm, not just call a library."

---

## SLIDE 4 — Team and languages (~40 s)

"Here is how we split the work — one language per person.

I did Java: the Raft core, the distributed training, and the desktop Watcher
interface.

Junior did Go: his Raft node and the record state machine that holds the log.

Andrew did Python: the CNN, the testing server and the video server, plus his Raft
node.

The key idea is at the bottom: all three nodes speak the same text protocol, so
even though they are different languages, they form one single heterogeneous
cluster. A Java node and a Go node talk to each other directly, with no
translation."

---

## SLIDE 5 — System architecture (~1.5 min)

"This diagram shows the full data flow, left to right.

On the left, three cameras produce frames. They feed the Testing Server, written in
Python, which runs the CNN.

When the CNN recognizes an object, that detection is sent into the Raft cluster —
the three nodes in the dashed box, Java, Python and Go. But it doesn't go to any
node: it goes through the leader.

The leader replicates that detection to the followers, and it becomes committed
once the majority has copied it. That's what keeps the log consistent across all
three machines.

Finally, on the right, the Watcher Client reads that committed, replicated log — it
never sees a half-written state.

So the whole system is: cameras produce, the CNN recognizes, Raft replicates, and
the Watcher displays."

> Punto tecnico si preguntan:
> "Every write goes through the leader; reads also go to the leader so the client
> always sees a consistent view."

---

## SLIDE 6 — Raft: leader election and log replication (~2 min)

"Now the consensus itself. In Raft, every node is in one of three states: Follower,
Candidate, or Leader — you can see the transitions in this diagram.

Leader election uses a randomized timeout, between 150 and 300 milliseconds. The
randomness is important: it avoids two nodes becoming candidates at the same time
and splitting the vote.

A candidate sends RequestVote messages. There's an election restriction: a node
only grants its vote if the candidate's log is at least as up to date as its own —
this guarantees the new leader has all committed entries.

Once elected, the leader uses AppendEntries to replicate. An entry is only
committed when it's on a majority of nodes.

To repair followers that fell behind, the leader tracks a nextIndex per follower
and uses the Log Matching property to bring them back in sync.

And one subtle rule from the paper: a leader only commits entries from its own
current term by counting replicas — this avoids a known edge case where an older
entry could be overwritten."

> Si preguntan "por que el timeout aleatorio?":
> "If all followers timed out at the same time, they'd all become candidates and
> split the vote forever. Random timeouts make one node start first and usually
> win."

Al terminar la slide 6, pasa la palabra a Junior:
"Junior will now show the exact protocol our nodes use."

---

## Tips

- Slide 5 es la mas importante tuya: es el diagrama que conecta todo. Senala con el
  cursor: cameras -> testing server -> cluster -> watcher.
- Slide 6 es densa (Raft). No leas los bullets; explica el flujo: elige lider ->
  replica -> commit por mayoria -> repara followers.
- Habla lento en la 5 y la 6, son las tecnicas.
