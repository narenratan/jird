Text files
==========

Playing a text file
-------------------
Jird can play music stored in text files. Take this example of some
chords over a bassline:

.. literalinclude:: ../../music/music_example

Say we have this music saved in a file `music.txt`. We can play it
by running

.. code:: console

    $ jird music.txt

Any alphabetic characters (A-Z,a-z) in the file are ignored so can be
used anywhere as titles, part labels, comments, etc.

To recap syntax, semicolons ; separate simultaneous parts. Notes are
written as `f:d:v` where `f` is the frequency ratio, `d` the duration,
and `v` the volume (and `:v` can be omitted). Chords are written as
`<f g h>:d:v` where `f`, `g`, `h`, are the frequency ratios of the
notes in the chord, `d` is the duration, and `v` the volume (and `:v`
can again be omitted).

Using multiplication
---------------------
The example music in MORSEL above shows using multiplication to transpose
the bass part down two octaves by dividing all frequencies by four.

Also in the chords the root notes are factored out so we can easily see
the root note separately from the intervals in the chord. So the chord
9/8*<1 9/8 5/4 3/2>:2 is a chord with root note 9/8, containing the root
1, major second 9/8, major third 5/4, and perfect fifth 3/2. This would
be less apparent if the chord was written as <9/8 81/64 45/32 27/16>:2.

.. _playback:

Controlling playback
--------------------
We can play the music slower by setting the time unit `t` to be longer
than the default 0.5 seconds:

.. code:: console

    $ jird -t 0.75 music.txt


We can set the frequency unit `f` to transpose the whole piece. The
default is to take frequency ratio `1/1` as being A 440Hz. To change
this to middle C at 261.31Hz we can run

.. code:: console

    $ jird -f 261.31 music.txt

By default jird used Fluidsynth for playback. We can specify which midi
instruments to use by passing a comma-separated list of general midi
program numbers with `-p`. For example to use harp (program number 47)
and acoustic bass (program number 33) we can run

.. code:: console

    $ jird -p 47,33 music.txt

Jird can also use Surge XT and ZynAddSubFX for playback; for details
see :doc:`synth_tutorial`.
