FONT=fonts/AlcarinTengwar-Regular.otf
PY=python3 -I
# full chain from the font to the PDF, the STL files and the web page; `make clean all` rebuilds everything
all: main.pdf web

data/codes.json: tools/measure.py tools/inventory.py tools/measure_helpers.py $(FONT)
	$(PY) tools/measure.py $(FONT) data
data/strokes.json: tools/strokes.py data/codes.json
	$(PY) tools/strokes.py $(FONT) data data/strokes.json
gen/analysis.json: data/codes.json tools/analysis.py
	$(PY) tools/analysis.py data gen
gen/analysis_fdm.json: tools/analysis_fdm.py
	$(PY) tools/analysis_fdm.py gen
gen/stats.json: data/codes.json data/strokes.json gen/analysis.json gen/analysis_fdm.json tools/gen_shuttle.py tools/layout.py tools/inventory.py
	$(PY) tools/gen_shuttle.py $(FONT) data gen
gen/fdmsim.json: tools/fdmsim.py data/codes.json
	$(PY) tools/fdmsim.py $(FONT) data gen
gen/fdmsim_thick.json: tools/fdmsim_thick.py tools/thicken.py data/codes.json
	$(PY) tools/fdmsim_thick.py $(FONT) data gen
gen/fdm_panel.png: tools/fdmpanel.py
	$(PY) tools/fdmpanel.py $(FONT) gen/fdm_panel.png
gen/fdm_panel2.png: tools/fdmpanel2.py tools/thicken.py
	$(PY) tools/fdmpanel2.py $(FONT) gen/fdm_panel2.png
stl/stamps.json: gen/stats.json tools/stamps.py tools/thicken.py tools/glyphgeom.py
	$(PY) tools/stamps.py $(FONT) data gen stl
gen/tab_stamps.tex: gen/fdmsim.json stl/stamps.json tools/tables_fdm.py
	$(PY) tools/tables_fdm.py gen stl

MODEL_DEPS=gen/stats.json tools/model/*.py tools/items.py tools/fontprof.py tools/fontsets.py tools/layout.py \
  data/inscription.json data/device/device_regions.json
# rev. 0.12: the case's inscription (transcribed by the page's transcriber) and the device's colour regions
data/inscription.json: tools/inscription.py tools/web/transcribe.js
	$(PY) tools/inscription.py data/inscription.json
data/device/device_regions.json: tools/device.py data/device/nyankonyan_elvish_device_v12_rope.svg
	$(PY) tools/device.py data/device/nyankonyan_elvish_device_v12_rope.svg data/device/device_regions.json
gen/model/model.json: $(MODEL_DEPS)
	$(PY) tools/model/build.py gen/model gen
# rev. 0.11: font sets of the shuttle (tools/fontsets.py): blocks, combs, checks, page data for every font
FONTSETS=alcarin hanno nenya miriel miriel-bold miriel-italic miriel-bolditalic racina pixel comixanesse annatar annatar-bold parmaite reformalized sindarin elfica eldamar telcontar telcontar-bold formal freemono miue
FONT_REPORTS=$(foreach f,$(FONTSETS),gen/fonts/$(f)/report.json)
gen/fonts/%/report.json: gen/model/model.json tools/model/fontset.py
	TPM_FONT=$* $(PY) tools/model/fontset.py gen/fonts
gen/tab_fonts.tex: $(FONT_REPORTS) tools/model/fonttab.py
	$(PY) tools/model/fonttab.py gen
fonts: $(FONT_REPORTS)
gen/freq.json: tools/model/freq.py tools/layout.py data/freq_books.json
	$(PY) tools/model/freq.py gen/freq.json
gen/freq_num.tex: gen/freq.json tools/model/freqtab.py tools/layout.py
	$(PY) tools/model/freqtab.py gen
gen/motor.json: gen/model/model.json gen/freq.json tools/model/motor.py
	$(PY) tools/model/motor.py gen/motor.json
gen/whiffle.json: tools/model/whiffle.py tools/model/params.py
	$(PY) tools/model/whiffle.py gen/whiffle.json
gen/links.json: tools/model/links.py tools/model/params.py
	$(PY) tools/model/links.py gen/links.json
gen/visibility.json: gen/model/model.json tools/model/visibility.py
	$(PY) tools/model/visibility.py gen/visibility.json gen
gen/tab_model_buy.tex: gen/model/model.json gen/motor.json gen/whiffle.json gen/links.json gen/visibility.json tools/model/tables.py
	$(PY) tools/model/tables.py gen
gen/read_num.tex: gen/model/model.json gen/motor.json tools/model/readtab.py tools/model/reader.py
	$(PY) tools/model/readtab.py gen
gen/model/renders/read_head.png: gen/model/model.json tools/model/readrender.py
	$(PY) tools/model/readrender.py gen/model

# rev. 0.13: physics checks (docs/physics_checks_spec.md): stage 1 -- joints, bodies, statics; stage 2 -- dynamics by node
PHYS=tools/physics
gen/physics/rest.npz: gen/model/model.json $(PHYS)/snapshot.py
	$(PY) $(PHYS)/snapshot.py
gen/physics/pairs.json: gen/physics/rest.npz $(PHYS)/candidates.py $(PHYS)/meshes.py
	$(PY) $(PHYS)/candidates.py
gen/physics/mass.json: gen/physics/rest.npz $(PHYS)/mass.py
	$(PY) $(PHYS)/mass.py
data/springs.json: $(PHYS)/springs.py gen/links.json gen/motor.json
	$(PY) $(PHYS)/springs.py
data/joints.json: gen/physics/pairs.json $(PHYS)/classify.py $(PHYS)/rules.py
	$(PY) $(PHYS)/classify.py
gen/physics/stage1.json: data/joints.json data/springs.json gen/physics/mass.json $(PHYS)/stage1.py $(PHYS)/stage1_run.py $(PHYS)/contactgeo.py
	rm -f gen/physics/patches_rest.pkl && $(PY) $(PHYS)/stage1_run.py
gen/tab_stage1.tex: gen/physics/stage1.json
gen/physics/node_c.json: gen/physics/mass.json gen/links.json gen/motor.json $(PHYS)/node_c.py
	$(PY) $(PHYS)/node_c.py
gen/physics/node_d.json: gen/physics/mass.json gen/motor.json $(PHYS)/node_d.py
	$(PY) $(PHYS)/node_d.py
gen/physics/node_b.json: gen/physics/mass.json gen/physics/node_c.json gen/motor.json gen/links.json $(PHYS)/node_b.py
	$(PY) $(PHYS)/node_b.py
gen/physics/node_a.json: gen/physics/mass.json gen/links.json $(PHYS)/node_a.py
	$(PY) $(PHYS)/node_a.py
gen/physics/node_f.json: gen/physics/node_b.json $(PHYS)/node_f.py
	$(PY) $(PHYS)/node_f.py
gen/physics/node_e.json: gen/physics/node_b.json $(PHYS)/node_e.py
	$(PY) $(PHYS)/node_e.py
gen/physics/node_g.json: gen/physics/stage1.json gen/physics/node_c.json $(PHYS)/node_g.py
	$(PY) $(PHYS)/node_g.py
NODES=$(foreach n,c d b a f e g,gen/physics/node_$(n).json)
gen/tab_stage2.tex: $(NODES) $(PHYS)/stage2_tab.py
	$(PY) $(PHYS)/stage2_tab.py
# stage 2b (spec §5б): the nodes on the cycle shaft's real law; the variants and the proposed set (the author decides)
gen/physics/stage2b.json: $(NODES) gen/motor.json data/springs.json $(PHYS)/shaft.py $(PHYS)/stage2b.py
	$(PY) $(PHYS)/stage2b.py
gen/tab_stage2b.tex: gen/physics/stage2b.json
gen/physics/stage2b_variants.json: gen/physics/stage2b.json $(PHYS)/stage2b_variants.py
	$(PY) $(PHYS)/stage2b_variants.py
gen/physics/stage2b_package.json: gen/physics/stage2b.json $(PHYS)/stage2b_package.py
	$(PY) $(PHYS)/stage2b_package.py
# the variants and the proposed set were the record of the decision (taken in rev. 0.14, stage 2b): built on demand only
physics: gen/tab_stage1.tex gen/tab_stage2.tex gen/tab_stage2b.tex

TEX_IN=gen/tab_stage1.tex gen/tab_stage2.tex gen/tab_stage2b.tex gen/tab_fonts.tex gen/freq_num.tex gen/stats.json gen/fdmsim_thick.json gen/fdm_panel.png gen/fdm_panel2.png gen/tab_stamps.tex gen/tab_model_buy.tex gen/read_num.tex gen/model/renders/read_head.png
main.pdf: main.tex preamble.tex $(TEX_IN)
	xelatex -interaction=nonstopmode main.tex >/dev/null; xelatex -interaction=nonstopmode main.tex | grep -E "^!|Output written" || true

gen/web/model.json: gen/model/model.json gen/motor.json tools/model/webexport.py
	mkdir -p gen/web && $(PY) tools/model/webexport.py gen/web/model.json
# the page and its data file tpm2-model-data.js; `make web-single` gives one self-contained file instead
WEB_SRC=tools/web/page.html tools/web/transcribe.js tools/web/viewer.js tools/web/viewer.css tools/web/build_page.py
gen/web/tpm2-model.html: gen/web/model.json $(WEB_SRC) $(FONT_REPORTS)
	$(PY) tools/web/build_page.py gen/web/model.json tools/web gen/web/tpm2-model.html
gen/web/tpm2-model-single.html: gen/web/model.json $(WEB_SRC) $(FONT_REPORTS)
	$(PY) tools/web/build_page.py gen/web/model.json tools/web gen/web/tpm2-model-single.html --single
web: gen/web/tpm2-model.html
web-single: gen/web/tpm2-model-single.html
# readable geometry (plain integer arrays, one line per shape) in its own folder
gen/web-plain/tpm2-model.html: gen/web/model.json $(WEB_SRC) $(FONT_REPORTS)
	mkdir -p gen/web-plain && $(PY) tools/web/build_page.py gen/web/model.json tools/web gen/web-plain/tpm2-model.html --plain
web-plain: gen/web-plain/tpm2-model.html
stl: stl/stamps.json
model: gen/tab_model_buy.tex

# rev. 0.14: zip whose file names unpack on Android/Windows/macOS (tools/pack.py checks them)
pack:
	cd .. && $(PY) $(CURDIR)/tools/pack.py $(notdir $(CURDIR)) $(notdir $(CURDIR))-full.zip
clean:
	find gen -maxdepth 1 -type f -delete; rm -rf gen/model gen/web gen/web-plain main.aux main.toc main.out main.pdf
.PHONY: all web web-single web-plain stl model physics pack clean
