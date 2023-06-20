Synths
======

Jird can use Fluidsynth, Surge XT, and ZynAddSubFX to render music
directly from the command line.

Specifying a synth
------------------
The `--synth` flag selects a synth to use (with a default patch). The
possible choices are `fluidsynth`, `zynaddsubfx`, and `surge_xt`. For
example running

.. code:: console

    $ jird --synth surge_xt

starts the interpreter using Surge XT for playback, and running

.. code:: console

    $ jird --synth zynaddsubfx music.txt

plays the music in music.txt with ZynAddSubFX.

Specifying an instrument
------------------------
We can specify a patch with the `-i` flag. The corresponding synth is
inferred from the patch filename. For example running

.. code:: console

    $ jird -i ~/surge/resources/data/patches_factory/Polysynths/Oiro.fxp

will start the interpreter using Surge XT with the Oiro patch for
playback. To play music in music.txt with this patch we can run

.. code:: console

    $ jird -i ~/surge/resources/data/patches_factory/Polysynths/Oiro.fxp music.txt

The Surge repo containing the patches can be found on
`github <https://github.com/surge-synthesizer/surge/>`_.

To use Zyn, we can run for example

.. code:: console

    $ jird -i /usr/share/zynaddsubfx/banks/the_mysterious_bank/0031-wah_sine.xiz

The Zyn patches may be found in /usr/share/zynaddsubfx/banks if you
have ZynAddSubFX installed. If not they can be found in the ZynAddSubFX
`instruments repo <https://github.com/zynaddsubfx/instruments>`_.

Using a config
--------------
More detailed synth configuration is done with a config file described
below. Given a config in config.json and music in music.txt, the music
can be played by running

.. code:: console

    $ jird -c config.json music.txt

The config allows specifying a different instrument for each jird part,
as well as setting overall parameters like the basic time and frequency.
For example, here is an example config with two parts:

.. code-block:: json

    {
        "t": 0.63,
        "f": 440.0,
        "synth": "surge_xt",
        "parts": [
            {
                "instrument": "~/surge/resources/data/patches_factory/Polysynths/Oiro.fxp",
                "volume": -8.25,
                "panning": 0.5
            },
            {
                "instrument": "~/surge/resources/data/patches_factory/Polysynths/Boss.fxp",
                "volume": -7.0,
                "panning": -0.5
            }
        ]
    }

With this config, one beat lasts 0.63 seconds, the frequency ratio
1/1 sounds at 440Hz, and Surge XT is used for playback.  The `parts`
list contains patches, volume, and panning to use for the two parts
(semicolon separated jird music).

Config fields
-------------
All config fields are described below.

.. autoclass:: jird.config.Config()

.. autoclass:: jird.config.PartConfig()
