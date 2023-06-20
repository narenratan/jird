Interactive mode
================

Various sharp fourth chords
---------------------------
Chords with a major third and sharp fourth, like CEF#, sound dreamy. In
just intonation there are various chords with this sort of sound. Let's
try some out!

The interpreter can be started by running

.. code-block:: console

    $ jird

Then entering

.. code::

  <1 5/4 10/7>:8

plays a chord for eight beats. The chord has three notes, the root 1,
the major third 5/4, and a 10/7 as the 'sharp fourth'.

We get a different sound with 11/8 as the sharp fourth:

.. code::

  <1 5/4 11/8>:8

Tasty! The 11/8 is audibly flatter than the 10/7.

Notes
-----
To confirm our impressions, we can print the notes by adding an `n` anywhere in the input.

.. code::

      <1 5/4 10/7>:8 n
    (
      [
        (
          Note(frequency=1, cents=0.0, duration=8),
          Note(frequency=5/4, cents=386.314, duration=8),
          Note(frequency=10/7, cents=617.488, duration=8),
        ),
      ],
    ),

So the root note 1 is at 0 cents (it's the reference point) and the major third 5/4 at 386 cents. The 10/7 is at 617 cents, sharper than the usual tritone which is 600 cents.

Looking at the chord with the 11/8,

.. code::

      <1 5/4 11/8>:8 n
    (
      [
        (
          Note(frequency=1, cents=0.0, duration=8),
          Note(frequency=5/4, cents=386.314, duration=8),
          Note(frequency=11/8, cents=551.318, duration=8),
        ),
      ],
    ),

we see that the 11/8 is 551 cents. So 11/8 (551 cents) is more than a quarter tone (50 cents) flatter than 10/7 (617 cents), as we heard.

Tables
------
We can see a table of the intervals between each note in a chord by adding a `t` to the input:

.. code::

      <1 5/4 10/7>:4 t

               1   5/4  10/7
          ------------------
       1  |    1   5/4  10/7
     5/4  |  4/5     1   8/7
    10/7  | 7/10   7/8     1

The table shows the interval from the note labeling the row up to the note labeling the column. So the 8/7 is there because the interval from 5/4 up to 10/7 is 8/7 -- because (10/7)/(5/4) = 8/7. An 8/7 is a wide sort of major second.

The interval table for the chord with 11/8 looks like

.. code::

                1    5/4   11/8
          ---------------------
       1  |     1    5/4   11/8
     5/4  |   4/5      1  11/10
    11/8  |  8/11  10/11      1

So in this case the interval from the major third 5/4 to the sharp fourth 11/8 is 11/10, a small sort of major second.

We can hear these different major seconds one after the other:

.. code::

    8/7:4 11/10:4

and see their frequencies:

.. code::

      8/7:4 11/10:4 n
    (
      [
        Note(frequency=8/7, cents=231.174, duration=4),
        Note(frequency=11/10, cents=165.004, duration=4),
      ],
    ),

so 8/7 is indeed sharper and 11/10 flatter than the usual major second at 200 cents.

Root played on bass
-------------------

Sometimes it's handy to hear a chord over a bass note. Running the interpreter as

.. code:: console

    $ jird -p 1,33

tells it to use midi program number 1 (acoustic grand piano) for the first part entered and program 33 (acoustic bass) for the second part.

Now entering

.. code::

    <5/4 10/7>:4; 1/4:4

we get a piano playing the two notes 5/4 and 10/7 and, at the same time, a bass playing 1/4 (two octaves below 1/1). The semicolon ; separates the notes in the two simultaneous parts.

Listening to the 11/8 version

.. code::

    <5/4 11/8>:4; 1/4:4

and experimenting with and without the bass note, you can hear the different seconds at the top of the chords.

For reference the full list of general midi instruments can be found `here <https://www.midi.org/specifications-old/item/gm-level-1-sound-set>`_.

Temperament
-----------
To hear tempered versions of the just intervals we can run the interpreter as, for example,

.. code:: console

    $ jird -e 19

The :code:`-e 19` says to approximate all notes as one of nineteen equal divisions of the octave (EDO). We get the usual twelve tone equal temperament with :code:`-e 12`.

Trying the 11/8 and 10/7 intervals in 19EDO and printing the note frequencies, we get

.. code::

      <1 11/8>:4 n
    (
      [
        (
          Note(frequency=2**0/19, cents=0.0, duration=4),
          Note(frequency=2**9/19, cents=568.421, duration=4),
        ),
      ],
    ),
      <1 10/7>:4 n
    (
      [
        (
          Note(frequency=2**0/19, cents=0.0, duration=4),
          Note(frequency=2**10/19, cents=631.579, duration=4),
        ),
      ],
    ),

Because we are in nineteen tone equal temperament all the frequency ratios are powers of 2**1/19. Here we see that 11/8 is approximated by nine steps of 19EDO, 10/7 by ten steps (so 11/8 is flatter than 10/7 by one step).

The same experiment with :code:`-e 12` shows that both 11/8 and 10/7 are approximated as 2**6/12 i.e. by six steps of twelve tone equal temperament, so we cannot distinguish them in 12EDO.
