import gradio as gr
from gradio.themes.utils import colors, fonts, sizes

# --- Define Delite AI Colors ---
# Dark Blue Scale
dark_blue_7 = "#040E1F"
dark_blue_6 = "#091933"
dark_blue_5 = "#12284C"
dark_blue_4 = "#1C355E"
dark_blue_3 = "#3C5989"
dark_blue_2 = "#6881AB"
dark_blue_1 = "#839ABE"

# Light Blue Scale
light_blue_7 = "#008D9F"
light_blue_6 = "#00A1B5"
light_blue_5 = "#00AEC5"
light_blue_4 = "#00BED6"
light_blue_3 = "#15CFE6"
light_blue_2 = "#34DEF4" # Primary Action Color
light_blue_1 = "#4DE3F6" # Lighter hover variant

# Orange Scale
orange_7 = "#BE5E00"
orange_6 = "#DD6D00"
orange_5 = "#EE7600"
orange_4 = "#FF7E00"
orange_3 = "#FF9025"
orange_2 = "#FFA54E"
orange_1 = "#FFB46A"

# Yellow Scale
yellow_7 = "#BA9C00"
yellow_6 = "#D8B500"
yellow_5 = "#E8C300"
yellow_4 = "#FED500"
yellow_3 = "#FFDC24"
yellow_2 = "#FFE24A"
yellow_1 = "#FFE768"

# Steel Scale
steel_7 = "#82B1CD"
steel_6 = "#A2C8DF"
steel_5 = "#B8D9EC"
steel_4 = "#D0EAF9"
steel_3 = "#DFF1FB"
steel_2 = "#F2FAFF"
steel_1 = "#F7FCFF"

# Gray Scale
gray_7 = "#484847" # Darkest Gray
gray_6 = "#5B5A59"
gray_5 = "#797877"
gray_4 = "#91908F" # Placeholder Gray
gray_3 = "#AFAFAE" # Border Gray
gray_2 = "#CBCBCB" # Secondary Button BG Gray
gray_1 = "#DFDFDF" # Background Gray

# Dark Gray Scale
dark_gray_7 = "#0A0807" # Darkest Text
dark_gray_6 = "#110F0D"
dark_gray_5 = "#1B1815"
dark_gray_4 = "#23201D" # Secondary Button Text
dark_gray_3 = "#2E2B29"
dark_gray_2 = "#3B3A38"
dark_gray_1 = "#535150"

# Red Scale
red_7 = "#A90707"
red_6 = "#BA0B0B"
red_5 = "#D21515"
red_4 = "#E41D1D"
red_3 = "#EE3737"
red_2 = "#F15D5D"
red_1 = "#F77D7D" # Alert

# Green Scale
green_7 = "#04A904"
green_6 = "#07BD07"
green_5 = "#0DD00D"
green_4 = "#16E916"
green_3 = "#37EF37"
green_2 = "#5DF55D"
green_1 = "#79F779" # Confirm

# --- Create Theme ---
delite_theme = gr.themes.Base(
    # Primary hue based on dark_blue_4
    primary_hue=gr.themes.Color(
        name="delite_dark_blue",
        c50="#E8ECF2",   # Approx Lightest
        c100=dark_blue_1, # #839ABE
        c200=dark_blue_2, # #6881AB
        c300=dark_blue_3, # #3C5989
        c400="#2A4775", # Approx between 3 and 4
        c500=dark_blue_4, # #1C355E - Main Action color
        c600=dark_blue_5, # #12284C
        c700="#0D1E3F", # Approx between 5 and 6
        c800=dark_blue_6, # #091933
        c900="#061329", # Approx between 6 and 7
        c950=dark_blue_7, # #040E1F - Darkest
    ),
    # Neutral hue based on the new Gray/Dark Gray palettes
    neutral_hue=gr.themes.Color(
        name="delite_gray",
        c50=gray_1,   # Background Gray
        c100="#D0D0D0",  # Approx
        c200=gray_2,   # Secondary Button BG
        c300=gray_3,   # Border / Secondary Hover
        c400=gray_4,   # Placeholder Text
        c500=gray_5,   # Mid Gray
        c600=gray_6,
        c700=gray_7,
        c800=dark_gray_2,
        c900=dark_gray_4, # Secondary Text
        c950=dark_gray_7, # Darkest Text
    ),
    secondary_hue=colors.gray, # Keep secondary fairly neutral
    font=[fonts.GoogleFont("Lato"), "ui-sans-serif", "system-ui", "sans-serif"],
    font_mono=[fonts.GoogleFont("Source Code Pro"), "ui-monospace", "Consolas", "monospace"],
    radius_size=sizes.radius_lg,
    spacing_size=sizes.spacing_md,
    text_size=sizes.text_md,

).set(
    # --- General ---
    body_background_fill="#FFFFFF", # White background
    body_text_color=dark_blue_4, # dark_blue_4 default text
    prose_header_text_weight="900",

    border_color_accent=dark_blue_4,
    border_color_primary=dark_blue_4,

    # --- Blocks ---
    block_background_fill=steel_2, # White block background
    block_border_width="2px",
    block_border_color=dark_blue_4, # dark_blue_4 border for blocks
    block_label_text_color=dark_blue_4, # dark_blue_4 label text
    block_label_background_fill="#FFFFFF", # White label background
    block_title_text_color=dark_blue_4, # dark_blue_4 title text
    # block_label_border_width="0px",
    # block_title_border_width="0px",
    # panel_border_width="0px",
    # checkbox_label_border_width="0px", # Remove border from checkbox label

    # --- Inputs / Outputs ---
    input_background_fill="#FFFFFF", # White input background
    input_border_color=dark_blue_4, # dark_blue_4 border
    input_border_width="0.4px",
    input_placeholder_color="*neutral_400", # gray_4 placeholder


    # --- Buttons ---
    button_border_width="0px",
    # Primary (Now Light Blue Button with Dark Blue Text)
    button_primary_background_fill=light_blue_4,
    button_primary_background_fill_hover=light_blue_6,
    button_primary_text_color="#FFFFFF",
    button_primary_border_color=dark_blue_4, # dark_blue_4 border

    # Secondary (White Button with Dark Blue Text)
    button_secondary_background_fill=dark_blue_4, # White background
    button_secondary_background_fill_hover=dark_blue_6, # Light gray hover
    button_secondary_text_color="#FFFFFF", # dark_blue_4 text
    button_secondary_border_color=dark_blue_4, # dark_blue_4 border

    # --- Specific Components ---
    checkbox_label_background_fill="#FFFFFF", # White background for label area
    checkbox_label_text_color=dark_blue_4, # dark_blue_4 text
    slider_color=dark_blue_4,
    slider_color_dark=dark_blue_4, # Ensure slider uses primary color

    # --- Special Colors ---
    color_accent_soft=green_1, # For confirmations
    panel_border_color=dark_blue_4,
    # panel_border_width="2px",
    table_border_color=dark_blue_4,

    # --- Potential Dark Mode (Commented Out - requires full palette definition) ---
    # body_background_fill_dark=dark_blue_7,
    # body_text_color_dark="white",
    # block_background_fill_dark="*neutral_900", # A dark gray from neutral scale
    # input_background_fill_dark="*neutral_800",
    # button_primary_text_color_dark="*neutral_950",
    # button_secondary_background_fill_dark="*neutral_700",
    # button_secondary_text_color_dark="white",
    button_cancel_background_fill=red_4,
    button_cancel_background_fill_hover=red_5,
    button_cancel_text_color="#FFFFFF",
    button_cancel_text_color_hover="#FFFFFF",
    button_cancel_border_color=red_4,
    button_cancel_border_color_hover=red_5,
)


# --- Example Usage ---
def greet(name, intensity):
    return f"Hello {name}! " * intensity

# Custom CSS for Tabs and Inputs
css = f"""

"""

with gr.Blocks(theme=delite_theme, css=css) as demo:
    gr.Markdown(
        """
        # Delite AI - Style Gradio Theme Demo
        This interface uses a theme inspired by the Delite AI style guide.
        Primary buttons are Dark Blue, text uses Dark Gray/Gray.
        """
    )
    with gr.Row():
        inp = gr.Textbox(label="Your Name", placeholder="Enter your name...")
        sld = gr.Slider(label="Intensity", minimum=1, maximum=5, step=1, value=2)
    with gr.Row():
         # Output in a distinct block
        with gr.Column(scale=3):
             out = gr.Textbox(label="Greeting")
        with gr.Column(scale=1):
             btn_primary = gr.Button("Greet", variant="primary")
             btn_secondary = gr.Button("Clear", variant="secondary")
             btn_cancel = gr.Button("Cancel", variant="cancel")


    btn_primary.click(fn=greet, inputs=[inp, sld], outputs=out)
    btn_secondary.click(fn=lambda: ["", 2, ""], inputs=None, outputs=[inp, sld, out]) # Clear inputs/outputs

    gr.Examples(
        [["Alice", 3], ["Bob", 1], ["Charlie", 5]],
        inputs=[inp, sld],
        outputs=out,
        fn=greet,
        cache_examples=False # Avoid caching issues during theme dev
    )

    with gr.Tabs():
        with gr.TabItem("First Tab"):
            gr.Markdown("Content for the first tab.")
            gr.Button("Button in Tab 1")
        with gr.TabItem("Second Tab"):
            gr.Radio(["X", "Y", "Z"], label="Options in Tab 2")

    with gr.Row():
        gr.Checkbox(label="Confirm Action")


# Launch the demo
if __name__ == "__main__":
    # Enable dark mode preference detection (optional)
    # demo.launch(debug=True) # Use debug=True to inspect CSS variables if needed
    demo.launch()