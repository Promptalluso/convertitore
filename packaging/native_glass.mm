#import <AppKit/AppKit.h>

// Liquid Glass (NSGlassEffectView) exists from macOS 26. It is looked up at run time so
// the bridge still builds with older SDKs and falls back to the classic vibrancy material.
static NSView *make_glass(NSRect frame, CGFloat cornerRadius) {
    Class glassClass = NSClassFromString(@"NSGlassEffectView");
    if (glassClass != nil) {
        NSView *glass = [[glassClass alloc] initWithFrame:frame];
        [glass setValue:@(cornerRadius) forKey:@"cornerRadius"];
        return glass;
    }
    NSVisualEffectView *glass = [[NSVisualEffectView alloc] initWithFrame:frame];
    glass.blendingMode = NSVisualEffectBlendingModeBehindWindow;
    glass.material = NSVisualEffectMaterialPopover;
    glass.state = NSVisualEffectStateActive;
    glass.wantsLayer = YES;
    glass.layer.cornerRadius = cornerRadius;
    glass.layer.masksToBounds = YES;
    return glass;
}

static bool insert_below(NSView *qtView, NSView *material) {
    NSView *parent = qtView.superview;
    NSWindow *window = qtView.window;
    if (parent == nil || window == nil) return false;
    window.opaque = NO;
    window.backgroundColor = NSColor.clearColor;
    material.frame = qtView.frame;
    material.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable;
    [parent addSubview:material positioned:NSWindowBelow relativeTo:qtView];
    return true;
}

// Floating controls such as the drop wheel: real Liquid Glass when available.
extern "C" bool convertitore_attach_glass(void *qtViewPointer, double cornerRadius) {
    if (qtViewPointer == nullptr) return false;
    NSView *qtView = (__bridge NSView *)qtViewPointer;
    return insert_below(qtView, make_glass(qtView.frame, cornerRadius));
}

// Regular windows and editors: Apple's translucent window material, as in Finder sidebars.
extern "C" bool convertitore_attach_window_material(void *qtViewPointer) {
    if (qtViewPointer == nullptr) return false;
    NSView *qtView = (__bridge NSView *)qtViewPointer;
    NSWindow *window = qtView.window;
    if (window == nil) return false;
    window.titlebarAppearsTransparent = YES;
    window.styleMask |= NSWindowStyleMaskFullSizeContentView;
    NSVisualEffectView *material = [[NSVisualEffectView alloc] initWithFrame:qtView.frame];
    material.blendingMode = NSVisualEffectBlendingModeBehindWindow;
    material.material = NSVisualEffectMaterialUnderWindowBackground;
    material.state = NSVisualEffectStateFollowsWindowActiveState;
    return insert_below(qtView, material);
}
