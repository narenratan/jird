integer: INT
ratio: integer ["/" integer]
ratio_product: ratio ("*" ratio)*
note: ratio ":" ratio_product [":" ratio]
chord: "<" [ratio_product]* ">" ":" ratio_product [":" ratio]
?atom: note | chord | "(" part ")"
?mult_expr: [ratio "*"]* atom
?pow_expr: mult_expr | mult_expr "**" ratio -> power
part: pow_expr*
music: part (";" part)*
?start: music

%import common.INT
%import common.WS
%import common.LETTER

%ignore WS
%ignore LETTER
