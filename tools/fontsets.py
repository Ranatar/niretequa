"""rev. 0.11: font sets of the shuttle. Every set is 11 type blocks and 11 code combs made from one font by the same
chain (tools/fontprof.py measures the font, tools/model/fontset.py builds and checks the set); the rest of the machine
is common. Alcarin is the design font: the document, the keycaps and every model check use it.
Fonts that do not fit the machine as it is (tools/fontprof.py says why):
  * rev. 0.11: Dan Smith's layout is read now (fontprof.raw_ds: the keymap, the axes from the tehtar's four widths);
    Annatar Italic and Bold Italic do not fit (letters 22 u wide, stems 8 mm under the line), Balgruf uses its own
    map (its axes come out left of the letters), Teleri is "all rights reserved" (not put into the repository);
  * rev. 0.11: CSUR fonts without mark anchors are read too (fontprof.raw_shaped: HarfBuzz shapes letter + tehta and
    the font's own placement gives the axis; where the font gives none, the outline does);
  * Tengwar Artano: its stems reach 7 mm under the line and its letters are up to 21 u wide; it fits only at 0.6 of
    Alcarin's size;
  * Oz's Wizard: lacks 14 of the machine's signs, among them the nasal bars, the dot below and the quotes, and is
    donationware (not put into the repository)."""
FONTSETS = [
    dict(id='alcarin', file='fonts/AlcarinTengwar-Regular.otf', name='Alcarin Tengwar', author='Toshi Omagari', lic='OFL'),
    dict(id='hanno', file='fonts/sets/TengwarHanno.ttf', name='Tengwar Hanno', author='Shankar Sivarajan (по Baloo 2)', lic='OFL'),
    dict(id='nenya', file='fonts/sets/TengwarNenya.ttf', name='Tengwar Nenya', author='Shankar Sivarajan', lic='—'),
    dict(id='miriel', file='fonts/sets/TengwarMiriel.ttf', name='Tengwar Miriel', author='Shankar Sivarajan (по Tellepsalinnacontar)', lic='—'),
    dict(id='miriel-bold', file='fonts/sets/TengwarMiriel-Bold.ttf', name='Tengwar Miriel Bold', author='Shankar Sivarajan', lic='—'),
    dict(id='miriel-italic', file='fonts/sets/TengwarMiriel-Ital.ttf', name='Tengwar Miriel Italic', author='Shankar Sivarajan', lic='—'),
    dict(id='miriel-bolditalic', file='fonts/sets/TengwarMiriel-BoldItalic.ttf', name='Tengwar Miriel Bold Italic', author='Shankar Sivarajan', lic='—'),
    dict(id='racina', file='fonts/sets/TengwarRacina.ttf', name='Tengwar Racina', author='Shankar Sivarajan (по Tengwar Gothika)', lic='—'),
    dict(id='pixel', file='fonts/sets/TengwarPixel.ttf', name='Tengwar Pixel', author='Shankar Sivarajan', lic='—'),
    dict(id='comixanesse', file='fonts/sets/TengwarComixanesse.ttf', name='Tengwar Comixanesse', author='Shankar Sivarajan', lic='—'),
    # rev. 0.11: Dan Smith's layout, axes estimated (fontprof.raw_ds)
    dict(id='annatar', file='fonts/sets/TengwarAnnatar.ttf', name='Tengwar Annatar', author='Johan Winge', lic='—', ds=True),
    dict(id='annatar-bold', file='fonts/sets/TengwarAnnatarBold.ttf', name='Tengwar Annatar Bold', author='Johan Winge', lic='—', ds=True),
    dict(id='parmaite', file='fonts/sets/Parmaite.ttf', name='Tengwar Parmaitë', author='Måns Björkman', lic='—', ds=True),
    dict(id='reformalized', file='fonts/sets/Tengwar-Reformalized.ttf', name='Tengwar Reformalized', author='Jakob Teuber', lic='—', ds=True),
    # rev. 0.11: CSUR without mark anchors, the axes from shaping (fontprof.raw_shaped, HarfBuzz)
    dict(id='eldamar', file='fonts/sets/Eldamar.ttf', name='Eldamar', author='Måns Björkman', lic='OFL', shaped=True),
    dict(id='eldamar-old', file='fonts/sets/tengel__.ttf', name='Tengwar Eldamar', author='Måns Björkman', lic='—', shaped=True),
    dict(id='formal', file='fonts/sets/TengwarFormalCSUR.ttf', name='Tengwar Formal CSUR', author='Michał Nowakowski', lic='—', shaped=True),
    dict(id='freemono', file='fonts/sets/FreeMonoTengwar-embedding.ttf', name='FreeMono Tengwar', author='GNU FreeFont', lic='GPL + font exception', shaped=True),
    dict(id='miue', file='fonts/sets/miue.ttf', name='miue serif', author='—', lic='—', shaped=True),
]
BY_ID = {f['id']: f for f in FONTSETS}
