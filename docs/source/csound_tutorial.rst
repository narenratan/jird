Csound
======

`Csound <https://csound.com/>`_ is a sound and music computing system.
Jird can output a Csound score corresponding to music written as
ratios. If we have some Jird music in a text file `music.txt`, running

.. code:: console

    $ jird --csound music.txt

will produce a Csound score file `music.sco`.

Then if `orchestra.orc` is a Csound orchestra file, running

.. code:: console

    $ csound orchestra.orc music.sco

will render the music to a wav file.

In the generated Csound score the fourth p-field is the volume of the
note and the fifth p-field is the frequency of the note in Hz. Below is
a simple one instrument Csound orchestra file which uses the volume `p4`
and frequency `p5` to set the amplitude and frequency for the `vco2`
Csound opcode:

.. literalinclude:: ../../music/orchestra.orc

**NB** the default note volume in Jird is 1, which if used as a Csound
oscillator amplitude can give quite a loud output. In the example
orchestra above the `0dbfs` reference level is set to 5 to give a
quieter output. For more information see the Csound `get started
<https://csound.com/get-started.html>`_ page.
