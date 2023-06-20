Core
====
.. automodule:: jird.core

Language
--------
Grammar and parsing is handled by the parsing library `lark
<https://lark-parser.readthedocs.io/>`_. The jird grammar is:

.. _grammar:
.. literalinclude:: ../../src/jird/jird.g

.. autofunction:: jird.core.parse

Music representation
--------------------

.. autoclass:: jird.core.Unevaluated
   :members:

.. autoclass:: jird.core.RatioProduct
   :members:

.. autoclass:: jird.core.Power
   :members:

.. autoclass:: jird.core.MidiNote
   :members:

.. autoclass:: jird.core.Note
   :members:

Temperament
-----------
.. autofunction:: jird.core.temper_note
.. autofunction:: jird.core.temper

Interval tables
---------------
.. autofunction:: jird.core.print_interval_table
.. autofunction:: jird.core.interval_table

Useful functions
----------------
.. autofunction:: jird.core.all_frequencies
.. autofunction:: jird.core.total_duration
.. autofunction:: jird.core.height
.. autofunction:: jird.core.lowest
.. autofunction:: jird.core.print_music
.. autofunction:: jird.core.apply_to_notes
.. autofunction:: jird.core.evaluate

Transformation from AST to Music
--------------------------------
.. autoclass:: jird.core.NoteTransformer

.. automethod:: jird.core.NoteTransformer.integer
.. automethod:: jird.core.NoteTransformer.ratio
.. automethod:: jird.core.NoteTransformer.ratio_product
.. automethod:: jird.core.NoteTransformer.mult_expr
.. automethod:: jird.core.NoteTransformer.power
.. automethod:: jird.core.NoteTransformer.note
.. automethod:: jird.core.NoteTransformer.chord
.. automethod:: jird.core.NoteTransformer.part
.. automethod:: jird.core.NoteTransformer.music
