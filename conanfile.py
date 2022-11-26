from conans import ConanFile, tools
import os


class Webrtc(ConanFile):
    name = "webrtc"
    license = "BSD"
    url = "https://github.com/CommonGroundAI/FSEngine"
    homepage = "https://www.commonground-ai.com/"
    author = "CommonGroundAI"
    description = "Chromium webrtc"
    settings = "os", "compiler", "build_type", "arch"
    options = {"with_h264": [True, False], "with_sdk": [True, False]}
    default_options = {"with_h264": False, "with_sdk": False}
    generators = []
    exports_sources = [".gclient", "patches/**"]
    short_paths = True
    revision_mode = "scm"

    @property
    def _depot_tools_dir(self):
        return os.path.join(self.source_folder, "depot_tools")

    @property
    def _webrtc_source_dir(self):
        return os.path.join(self.source_folder, "src")

    def configure(self):
        # webrtc using its own clang
        if self.settings.compiler == "clang":
            del self.settings.compiler

    def source(self):
        # download and configure depot_tools
        git_depot_tools = tools.Git(folder="depot_tools")
        git_depot_tools.clone(self.conan_data["sources"][self.version][0]["url"],
                              self.conan_data["sources"][self.version][0]["branch"])
        # download and configure webrtc
        with tools.environment_append({"PATH": [self._depot_tools_dir], "DEPOT_TOOLS_WIN_TOOLCHAIN": "0"}):
            self.run("echo 'target_os = %s' >> .gclient" % self._gclient_os())
            self.run("gclient sync --no_bootstrap --shallow --no-history -vv --revision %s" % self._gclient_revision())
        # run webrtc patches
        self._patches()

    def _patches(self):
        self.output.info("starting patches to webrtc")

        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            tools.patch(**patch)

        # https://groups.google.com/forum/#!topic/discuss-webrtc/f44XZnQDNIA
        # https://stackoverflow.com/questions/49083754/linking-webrtc-with-qt-on-windows
        # https://docs.conan.io/en/latest/reference/tools.html#tools-replace-in-file
        if self.settings.os == "Windows":
            with tools.chdir(self._webrtc_source_dir):
                build_gn_file = os.path.join('build', 'config', 'win', 'BUILD.gn')
                tools.replace_in_file(build_gn_file,
                                      'configs = [ ":static_crt" ]',
                                      'configs = [ ":dynamic_crt" ]')
        if self.settings.os == "Linux":
            with tools.chdir(self._webrtc_source_dir):
                clockdrift_detector_file = os.path.join(
                    'modules', 'audio_processing', 'aec3', 'clockdrift_detector.h')
                # missing `std::` won't compile with gcc10
                tools.replace_in_file(clockdrift_detector_file,
                                      ' size_t stability_counter_;',
                                      ' std::size_t stability_counter_;')

        # there is a `include <cstring>` missing when not compiling with
        # their stdcxx (`use_custom_libcxx`)
        with tools.chdir(self._webrtc_source_dir):
            stack_copier_signal_file = os.path.join('base', 'profiler', 'stack_copier_signal.cc')
            tools.replace_in_file(stack_copier_signal_file,
                                  '#include <syscall.h>',
                                  '''#include <syscall.h>
                                     #include <cstring>''')

    def _gclient_revision(self):
        from six import StringIO
        stdout = StringIO()
        self.run(
            "git ls-remote %s --heads %s | head -n 1 | cut -f 1" % (self.conan_data["sources"][self.version][1]["url"],
                                                                    self.conan_data["sources"][self.version][1][
                                                                        "branch"]),
            output=stdout)
        return stdout.getvalue()

    def _gn_os(self):
        if self.settings.os == "Windows":
            return "win"
        elif self.settings.os == "Linux":
            return "linux"
        elif self.settings.os == "Macos":
            return "mac"
        elif self.settings.os == "iOS":
            return "ios"
        else:
            raise Exception("not valid os: ", self.settings.os)

    def _gn_arch(self):
        if self.settings.arch == "x86_64":
            return "x64"
        elif self.settings.arch == "armv8":
            return "arm64"
        else:
            raise Exception("not valid arch: ", self.settings.arch)

    def _gclient_os(self):
        gn_os = self._gn_os()
        if self.settings.os == "iOS":
            return '["mac", "%s"]' % gn_os
        else:
            return '["%s"]' % gn_os

    def _gn_args(self):
        args = ['target_os=\\"%s\\"' % self._gn_os(), 'target_cpu=\\"%s\\"' % self._gn_arch(),
                'is_component_build=false', 'treat_warnings_as_errors=false',
                'rtc_build_examples=false', 'use_rtti=true',
                'rtc_build_tools=false', 'rtc_include_tests=false', 'libyuv_include_tests=false']
        if self.settings.build_type == "Release":
            args.extend(['is_debug=false', 'symbol_level=0'])
        elif self.settings.build_type == "RelWithDebInfo":
            args.extend(['is_debug=false', 'symbol_level=1'])
        if self.options.with_h264:
            args.extend(['rtc_with_h264=true', 'proprietary_codecs=true', 'ffmpeg_branding="Chrome"'])
        # add args by os
        if self.settings.os == "Windows":
            args.extend(['use_custom_libcxx=false',
                         'treat_warnings_as_errors=false'])
            if self.settings.build_type == "Debug":
                # if not set the compilation will fail with:
                # _iterator_debug_level value '0' doesn't match value '2'
                # does not compile if tests and tools gets compiled in!
                args.extend(['enable_iterator_debugging=true'])
        elif self.settings.os == "Linux":
            if self.settings.compiler == "gcc":
                args.extend(['is_clang=false', 'use_custom_libcxx=false'])
        elif self.settings.os == "Macos":
            args.extend(['is_clang=true', 'use_custom_libcxx=false', 'enable_dsyms=true'])
        elif self.settings.os == "iOS":
            args.extend(
                ['is_clang=true', 'use_custom_libcxx=false', 'enable_dsyms=true', 'ios_enable_code_signing=false'])
        else:
            raise Exception("not valid os: ", self.settings.os)
        return " ".join(args)

    def build(self):
        envs = {"PATH": [self._depot_tools_dir]}
        if self.settings.os == "Windows":
            envs["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
            envs["PYTHONIOENCODING"] = "utf-8"
            envs["GYP_MSVS_VERSION"] = "2019"
        with tools.environment_append(envs):
            with tools.chdir(self._webrtc_source_dir):
                self.output.info("args: %s" % self._gn_args())
                self.run("gn gen %s --args=\"%s\"" % (self.build_folder, self._gn_args()))
                self.run("gn args --list %s" % self.build_folder)  # show configuration
                self.run("ninja -v -C %s %s" % (self.build_folder, self._get_targets()))

    def _get_targets(self):
        targets = ['webrtc']
        if self.options.with_sdk:
            if self.settings.os in ["Macos", "iOS"]:
                if self.settings.os == "Macos":
                    targets.extend(['sdk:mac_framework_objc'])
                elif self.settings.os == "iOS":
                    targets.extend(['sdk:framework_objc'])
            elif self.settings.os == "Android":
                targets.extend([
                    'sdk/android:libwebrtc',
                    'sdk/android:libjingle_peerconnection_so',
                    'sdk/android:native_api',
                ])
        self.output.info("targets: %s" % targets)
        return " ".join(targets)

    def package(self):
        self.copy("*.h", dst="include", src="src")
        self.copy("*.inc", dst="include", src="src")

        if self.settings.os == "Windows":
            self.copy("*webrtc.lib", dst="lib", keep_path=False)
            self.copy("*webrtc.dll", dst="bin", keep_path=False)
        else:
            self.copy("*libwebrtc.so", dst="lib", keep_path=False)
            self.copy("*libwebrtc.dylib", dst="lib", keep_path=False)
            self.copy("*libwebrtc.a", dst="lib", keep_path=False)
            if self.settings.os in ["Macos", "iOS"]:
                self.copy("WebRTC.framework/*", dst=".", keep_path=True, symlinks=True)
                self.copy("WebRTC.dSYM/*", dst=".", keep_path=True, symlinks=True)

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        self.output.info("collected libs: %s" % self.cpp_info.libs)
        self.cpp_info.includedirs.extend(['include/third_party/abseil-cpp',
                                          'include/third_party/libyuv/include',
                                          'include/third_party/boringssl/src/include',
                                          ])
        if self.options.with_h264:
            self.cpp_info.defines.extend(["WEBRTC_with_h264"])
        # platform specific
        if self.settings.os == "Windows":
            self.cpp_info.defines.extend(['WEBRTC_WIN', 'WIN32_LEAN_AND_MEAN', 'NOMINMAX'])
            self.cpp_info.system_libs.extend(
                ["secur32", "winmm", "dmoguids", "wmcodecdspuuid", "msdmo", "Strmiids", "Iphlpapi.lib"])
        elif self.settings.os == "Linux":
            self.cpp_info.system_libs = ["dl"]
            self.cpp_info.defines.extend(["WEBRTC_POSIX", "WEBRTC_LINUX"])
            self.cpp_info.system_libs.extend(
                ["Xtst", "Xfixes", "Xrandr", "Xext", "Xcomposite", "Xdamage", "X11", "glib-2.0", "pthread"])
        elif self.settings.os == "Macos":
            self.cpp_info.defines.extend(["WEBRTC_POSIX", "WEBRTC_MAC"])
            self.cpp_info.frameworks.extend(["Foundation", "CoreServices", "CoreFoundation", "AppKit", "IOSurface"])
        elif self.settings.os == "iOS":
            self.cpp_info.defines.extend(["WEBRTC_POSIX", "WEBRTC_IOS", "WEBRTC_MAC"])
            self.cpp_info.frameworks.extend(
                ["AVFoundation", "CFNetwork", "Foundation", "Security", "SystemConfiguration", "UIKit"])
        else:
            raise Exception("not valid os: ", self.settings.os)
