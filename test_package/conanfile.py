from conans import ConanFile, CMake, tools
import os


class TestPackageConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake", "cmake_find_package"

    def system_requirements(self):
        packages = []
        if tools.os_info.is_linux and self.settings.os == "Linux":
            packages = ["libasound2-dev", "libpulse-dev", "libxdamage-dev", "libxrandr-dev", "libxtst-dev", "libxcomposite-dev", "libgbm-dev"]
        if packages:
            package_tool = tools.SystemPackageTool(conanfile=self, default_mode='verify')
            for p in packages:
                package_tool.install(update=True, packages=p)        

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self.settings):
            bin_path = os.path.join(os.getcwd(), "bin", "test_package")
            self.output.info("bin_path: %s" % bin_path)
            self.run(bin_path, run_environment=True)