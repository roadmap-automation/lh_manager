# Building the client

## Install nodejs
- `conda install nodejs`

## Install dependencies
_in (/static folder) - this only has to be done once_
- `npm install`

## Build client
_every time a change is made to the client code_
- `npm run build`

## Optionally, to do tracebacks in the GUI:
- `npm run build -- --sourcemap`