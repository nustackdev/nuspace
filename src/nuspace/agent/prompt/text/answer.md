The work cycle is over. You are in the **answer cycle** now.

Hand back one dict and write nothing:

    nu.Dict.of(cell=nu.Str(<the whole source of one Cell>), said=nu.Str(<one plain line>))

`cell` is what they see: what happened, and how they answer next, in one Cell.
`said` is the one line the conversation keeps. The host builds the Cell,
checks it, and appends it; a Cell that will not build comes back to you as
`THE CELL DID NOT BUILD` and you fix it and hand the dict back again.

`Run.done` does nothing here. The turn ends when the answer lands.

The ids you need are in the first message of this turn. Read "Answering" and
"Drawing an answer" again before you write the Cell.
