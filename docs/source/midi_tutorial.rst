Midi
====
Jird can output midi files to use with other music programs.

With scala files
----------------
If we have have music in text file `music.txt`, running

.. code:: console

    $ jird -m music.txt

will produce a midi file music.midi along with scala files music.scl
and music.kbm defining the tuning. Together these can be used to load
the music and tuning into a digital audio workstation (DAW). This needs
a synth which supports tuning with scala files, for example `Surge XT
<https://surge-synthesizer.github.io/>`_.

With pitch bends
----------------
To use synths which don't support scala files, we can retune with MIDI
pitch bends. Running

.. code:: console

    $ jird -m --tuning_method pitch_bend music.txt

will output a midi file music.midi which uses pitch bends to retune
each note.  If the synth uses Midi Polyphonic Expression (MPE), you may
need to set the pitch bend range to 48 semitones (48 is the MPE default;
jird by default uses two semitones):

.. code:: console

    $ jird -m --tuning_method pitch_bend --pitch_bend_range 48 music.txt
