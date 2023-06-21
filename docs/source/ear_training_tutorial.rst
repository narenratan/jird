Ear training
============

Training mode
-------------
Say we have the following ratios in a file `ratios.txt`

.. code::

    7/6
    6/5
    5/4
    9/7
    14/9
    8/5
    5/3
    12/7

We can practice recognizing the corresponding intervals (1/1 played
together with the given ratio) by running

.. code:: console

    $ jird --train ratios.txt

A randomly selected ratio from `ratios.txt` is then played, and a
'?' prompt printed. The trainee types in the ratio they think it is
(e.g. 7/6). If the guess is incorrect, the correct ratio is printed.
Otherwise a new randomly selected interval is played and the fun
continues.  Hit Ctrl-D to finish training and see your score.

A typical session looks like this:

.. code::

    JIRD - It's just intonation

    ? 14/9
    ? 5/4
    ? 8/5
    ? 5/4
    ? 5/3
    ? 7/6

    6/5

    ? 14/9
    Score: 6/7, 85.7%
    Thank you for using Jird!

Example interval sets
---------------------
The following training sets are chosen from nineteen just intervals (which
happen to be close to nineteen-tone equal temperament). The names are from
Harry Partch's `Genesis of a Music` - note these are "arbitrarily named
categories" grouped "according to psychological (or whimsical) reactions".

**Emotion**

.. literalinclude:: ../../training/emotion

**Approach**

.. literalinclude:: ../../training/approach

**Power and Suspense**

.. literalinclude:: ../../training/power_and_suspense

**Nineteen tones**

.. literalinclude:: ../../training/nineteen_tones

Controlling playback
--------------------
All options for :ref:`playback<playback>` can be used in ear training
mode too, for example `-f` to set the frequency of 1/1 and `-p` to set
the instrument sound used.
