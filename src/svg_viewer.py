import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.svg import SVGBackend
import xml.etree.ElementTree as ET
import base64

def get_interactive_svg_html(dxf_path: str, height: int = 600) -> str:
    """
    Reads a DXF file and converts it to an interactive SVG with pan/zoom enabled.
    """
    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        return f"<div>Error loading DXF for viewer: {e}</div>"
        
    msp = doc.modelspace()
    
    # 1. Setup the drawing backend
    backend = SVGBackend()
    # Adjust layout settings to get better line visibility
    from ezdxf.addons.drawing.properties import LayoutProperties
    from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
    
    # Force dark background, bright lines
    config = Configuration(
        background_policy=BackgroundPolicy.CUSTOM,
        custom_bg_color="#1a1a1a",
        color_policy=ColorPolicy.COLOR, 
    )
    
    ctx = RenderContext(doc)
    out = Frontend(ctx, backend, config=config)
    
    # 2. Render the modelspace
    out.draw_layout(msp, finalize=True)
    
    # 3. Get SVG string using ezdxf page layout
    from ezdxf.addons.drawing import layout
    page = layout.Page(1920, 1080)
    svg_str = backend.get_string(page, xml_declaration=False)
    
    # We need to insert the id="cad-svg" and width/height 100% into the root <svg> tag
    # to make it play nicely with svg-pan-zoom
    svg_str = svg_str.replace('<svg ', '<svg id="cad-svg" width="100%" height="100%" ', 1)
    
    # 4. Wrap with svg-pan-zoom.js HTML wrapper
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background-color: #1a1a1a; overflow: hidden; font-family: sans-serif; }}
            #svg-container {{ width: 100%; height: {height}px; }}
            svg {{ width: 100%; height: 100%; }}
            .overlay {{ position: absolute; top: 10px; right: 10px; color: white; background: rgba(0,0,0,0.5); padding: 5px 10px; border-radius: 4px; font-size: 12px; pointer-events: none; }}
        </style>
    </head>
    <body>
        <div id="svg-container">
            {svg_str}
        </div>
        <div class="overlay">CAD Viewer (Scroll to Zoom, Click+Drag to Pan)</div>
        <script>
            window.onload = function() {{
                var svgPanZoomOptions = {{
                    controlIconsEnabled: true,
                    zoomEnabled: true,
                    panEnabled: true,
                    fit: true,
                    center: true,
                    minZoom: 0.1,
                    maxZoom: 50,
                    zoomScaleSensitivity: 0.2
                }};
                
                var panZoom = svgPanZoom('#cad-svg', svgPanZoomOptions);
                
                setTimeout(function() {{
                    panZoom.resize();
                    panZoom.fit();
                    panZoom.center();
                }}, 100);
            }};
        </script>
    </body>
    </html>
    """
    
    return html
