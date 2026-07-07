# Nodo Go — Máquina de estado del registro + nodo Raft

Parte de Junior. Todo con `net` + goroutines + `sync` de la stdlib, sin frameworks.

## Estructura

```
raft/nodo.go   nodo Raft en Go (mismo protocolo que Java y Python)
main.go        lanza el nodo
go.mod         modulo finalcc4p1
```

## Compilar y correr un nodo

```bash
cd go
go build -o gonodo .
./gonodo 3  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

O directo con `go run`:

```bash
go run . 3  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

El nodo mantiene la maquina de estado del registro protegida con mutex, asi las
detecciones no se corrompen aunque lleguen concurrentes.

## Ver el detalle de como esta hecho

`docs/COMO-LO-HICE.md` en la raiz del repo.
