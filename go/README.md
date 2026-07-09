# Nodo Go (Junior)

Maquina de estado del registro + nucleo Raft en Go. Ver [PLANIFICACION.md](../PLANIFICACION.md).

Sockets TCP crudos (`net.Listen` / `net.Dial`) e hilos nativos de Go
(goroutines + mutex), sin frameworks ni librerias externas — solo la
biblioteca estandar. Habla el mismo protocolo de texto que Java y Python
(documentado en [`java/src/raft/Protocolo.java`](../java/src/raft/Protocolo.java)),
asi que un nodo Go interopera con nodos Java o Python en el mismo cluster.

## Estructura

```
go/
  go.mod
  internal/raft/
    protocolo.go   mensajes del protocolo en texto (mismo formato que Java/Python)
    entrada.go     una entrada del log replicado (term + comando)
    par.go         direccion host:puerto de otro nodo del cluster
    registro.go    maquina de estado: registro de detecciones ya aplicado,
                    con su propio mutex para servir lecturas consistentes
    nodo.go        nucleo Raft: eleccion, replicacion, commit por mayoria,
                    atencion de conexiones entrantes (una goroutine por conexion)
    cliente.go     cliente de cluster (sigue REDIRECT hasta dar con el lider)
  cmd/
    arrancar-nodo/  levanta un nodo Raft en Go
    prueba-e2e/     prueba end-to-end del nucleo (3 nodos Go en un proceso)
    interop-check/  cliente de linea de comandos para probar contra
                    cualquier cluster (Go, Java o mixto)
```

## Probar el nucleo Raft de una

Levanta 3 nodos Go en un solo proceso, inserta detecciones, mata al lider,
verifica reeleccion y consistencia (igual que `raft.PruebaE2E` en Java):

```bash
cd go && go run ./cmd/prueba-e2e
```

## Levantar un nodo

```bash
cd go && go run ./cmd/arrancar-nodo <miId> <id:host:puerto> ...
```

Ejemplo, cluster de 3 nodos en la misma maquina (todos Go):

```bash
go run ./cmd/arrancar-nodo 1 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
go run ./cmd/arrancar-nodo 2 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
go run ./cmd/arrancar-nodo 3 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

El mismo comando funciona en un cluster mixto: basta con que los demas ids
de la lista sean nodos Java (`java raft.ArrancarNodo ...`) o Python
escuchando en esos puertos — el protocolo de texto es el mismo. Probado a
mano con un cluster de 2 nodos Java + 1 nodo Go: el nodo Go vota, replica y
aplica entradas que vienen de un lider Java sin cambios en el protocolo.

## Probar contra un cluster ya levantado (interop)

`interop-check` inserta una deteccion y lee el registro contra cualquier
cluster que hable el protocolo (util para validar interoperabilidad con
Java o Python):

```bash
cd go && go run ./cmd/interop-check 1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

## Maquina de estado del registro

`RegistroDetecciones` (en `internal/raft/registro.go`) es la parte que le da
sentido al consenso: solo guarda las detecciones cuyo indice de log ya fue
cometido por mayoria, y las aplica en orden estricto de indice. Tiene su
propio mutex, separado del mutex del nucleo Raft, para que una lectura del
Vigilante (`LEER_REGISTRO`) nunca vea un estado a medio escribir mientras
otra goroutine sigue aplicando entradas nuevas.

## Notas de implementacion

- Timeout de eleccion aleatorio 150-300 ms y heartbeat cada 50 ms, igual que
  la referencia Java.
- La mayoria se calcula como en el paper: `(pares+1)/2 + 1` sobre el total
  del cluster (yo + mis pares).
- Un indice solo se comete si esta replicado en la mayoria Y pertenece al
  term actual del lider (no se cuentan replicas de entradas de terms
  pasados para cometer).
- El `NUEVA_DETECCION` y `LEER_REGISTRO` devuelven `REDIRECT|host:puerto`
  si el nodo contactado no es el lider, igual que Java y Python deben hacer.
