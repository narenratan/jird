Installation
============

Currently only Linux is supported. Package names and install commands
are given for Debian/Ubuntu.

Minimal
-------
#.  Download the jird executable from the github `release page
    <https://github.com/narenratan/jird/releases>`_.

#.  Install rlwrap and fluidsynth

    .. code-block:: console

        $ sudo apt-get install rlwrap fluidsynth

    On Debian and Ubuntu fluidsynth comes set up with a default
    soundfont. If your distro doesn't do this, you can add

    .. code:: console

        export JIRD_SOUNDFONT=<path_to_soundfont>

    to your `.bashrc` or equivalent, where `<path_to_soundfont>` is the
    path to the soundfont you would like to use by default.

#.  Define a shell alias like

    .. code:: console

        alias jird='rlwrap <path_to_jird>'

    in your `.bashrc` or equivalent. Here `<path_to_jird>` is the path to
    the downloaded jird executable. This alias is to run jird under rlwrap
    for input editing and history.

Extra
-----
To allow using the Surge XT and ZynAddSubFX synths:

#.  Clone the Surge XT repo (for the patch library)

    .. code-block:: console

        $ git clone https://github.com/surge-synthesizer/surge.git

#.  Install ZynAddSubFX and ALSA utils (for aplaymidi and aplay)

    .. code-block:: console

        $ sudo apt-get install zynaddsubfx alsa-utils
