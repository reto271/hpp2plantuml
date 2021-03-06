# %% Imports

import os
import re
import glob
import argparse
import CppHeaderParser
import jinja2

# %% Constants


# Association between member property and PlantUML symbol
MEMBER_PROP_MAP = {
    'private': '-',
    'public': '+',
    'protected': '#'
}

# Links
LINK_TYPE_MAP = {
    'inherit': '<|--',
    'aggregation': 'o--',
    'composition': '*--',
    'dependency': '<..'
}

# Association between object names and objects
# - The first element is the object type name in the CppHeader object
# - The second element is the iterator used to loop over objects
# - The third element is a function returning the corresponding internal object
CONTAINER_TYPE_MAP = [
    ['classes', lambda objs: objs.items(), lambda obj: Class(obj)],
    ['structs', lambda objs: objs.items(), lambda obj: Struct(obj)],
    ['enums', lambda objs: objs, lambda obj: Enum(obj)]
]

# %% Base classes


class Container(object):
    """Base class for C++ objects

    This class defines the basic interface for parsed objects (e.g. class).
    """
    def __init__(self, container_type, name):
        """Class constructor

        Parameters
        ----------
        container_type : str
            String representation of container type (``class``, ``struct`` or
            ``enum``)
        name : str
            Object name
        """
        self._container_type = container_type
        self._name = name
        self._member_list = []
        self._namespace = None

    def get_name(self):
        """Name property accessor

        Returns
        -------
        str
            Object name
        """
        return self._name

    def parse_members(self, header_container):
        """Initialize object from header

        Extract object from CppHeaderParser dictionary representing a class, a
        struct or an enum object.  This extracts the namespace.

        Parameters
        ----------
        header_container : CppClass, CppStruct or CppEnum
            Parsed header for container
        """
        namespace = header_container.get('namespace', None)
        if namespace:
            self._namespace = re.sub(':+$', '', namespace)
        self._do_parse_members(header_container)

    def _do_parse_members(self, header_container):
        """Initialize object from header (abstract method)

        Extract object from CppHeaderParser dictionary representing a class, a
        struct or an enum object.

        Parameters
        ----------
        header_container : CppClass, CppStruct or CppEnum
            Parsed header for container
        """
        raise NotImplementedError(
            'Derived class must implement :func:`_do_parse_members`.')

    def render(self):
        """Render object to string

        Returns
        -------
        str
            String representation of object following the PlantUML syntax
        """
        container_str = self._render_container_def() + ' {\n'
        for member in self._member_list:
            container_str += '\t' + member.render() + '\n'
        container_str += '}\n'
        if self._namespace is not None:
            return wrap_namespace(container_str, self._namespace)
        return container_str

    def comparison_keys(self):
        """Order comparison key between `ClassRelationship` objects

        Use the parent name, the child name then the link type as successive
        keys.

        Returns
        -------
        list
            `operator.attrgetter` objects for successive fields used as keys
        """
        return self._container_type, self._name

    def sort_members(self):
        """Sort container members

        sort the list of members by type and name
        """
        self._member_list.sort(key=lambda obj: obj.comparison_keys())

    def _render_container_def(self):
        """String representation of object definition

        Return the definition line of an object (e.g. "class MyClass").

        Returns
        -------
        str
            Container type and name as string
        """
        return self._container_type + ' ' + self._name

# %% Object member


class ContainerMember(object):
    """Base class for members of `Container` object

    This class defines the basic interface for object members (e.g. class
    variables, etc.)
    """
    def __init__(self, header_member, **kwargs):
        """Constructor

        Parameters
        ----------
        header_member : str
            Member name
        """
        self._name = header_member
        self._type = None

    def render(self):
        """Render object to string (abstract method)

        Returns
        -------
        str
            String representation of object member following the PlantUML
            syntax
        """
        raise NotImplementedError('Derived class must implement `render`.')

    def comparison_keys(self):
        """Order comparison key between `ClassRelationship` objects

        Use the parent name, the child name then the link type as successive
        keys.

        Returns
        -------
        list
            `operator.attrgetter` objects for successive fields used as keys
        """
        if self._type is not None:
            return self._type, self._name
        else:
            return self._name

# %% Class object


class Class(Container):
    """Representation of C++ class

    This class derived from `Container` specializes the base class to handle
    class definition in C++ headers.

    It supports:

    * abstract and template classes
    * member variables and methods (abstract and static)
    * public, private, protected members (static)
    """
    def __init__(self, header_class):
        """Constructor

        Extract the class name and properties (template, abstract) and
        inheritance.  Then, extract the class members from the header using the
        :func:`parse_members` method.

        Parameters
        ----------
        header_class : list (str, CppClass)
            Parsed header for class object (two-element list where the first
            element is the class name and the second element is a CppClass
            object)
        """

        print("iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")
        print("   header_class")
        print(header_class)
        print("iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")
        print(header_class[0])
        print("iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")


        #super().__init__('class', header_class[0])
        #super(Container, self).__init__('class', header_class[0])
        #super(Container, self, 'class', header_class[0]).__init__()
        Container.__init__(self, 'class', header_class[0])

        self._abstract = header_class[1]['abstract']
        self._template_type = None
        if 'template' in header_class[1]:
            self._template_type = _cleanup_single_line(
                header_class[1]['template'])
        self._inheritance_list = [re.sub('<.*>', '', parent['class'])
                                  for parent in header_class[1]['inherits']]
        self.parse_members(header_class[1])

    def _do_parse_members(self, header_class):
        """Initialize class object from header

        This method extracts class member variables and methods from header.

        Parameters
        ----------
        header_class : CppClass
            Parsed header for class
        """
        member_type_map = [
            ['properties', ClassVariable],
            ['methods', ClassMethod]
        ]
        for member_type, member_type_handler in member_type_map:
            for member_prop in MEMBER_PROP_MAP.keys():
                member_list = header_class[member_type][member_prop]
                for header_member in member_list:
                    self._member_list.append(
                        member_type_handler(header_member, member_prop))

    def build_variable_type_list(self):
        """Get type of member variables

        This function extracts the type of each member variable.  This is used
        to list aggregation relationships between classes.

        Returns
        -------
        list(str)
            List of types (as string) for each member variable
        """
        variable_type_list = []
        for member in self._member_list:
            if isinstance(member, ClassVariable):
                variable_type_list.append(member.get_type())
        return variable_type_list

    def build_inheritance_list(self):
        """Get inheritance list

        Returns
        -------
        list(str)
            List of class names the current class inherits from
        """
        return self._inheritance_list

    def _render_container_def(self):
        """Create the string representation of the class

        Return the class name with template and abstract properties if
        present.  The output string follows the PlantUML syntax.

        Returns
        -------
        str
            String representation of class
        """
        class_str = self._container_type + ' ' + self._name
        if self._abstract:
            class_str = 'abstract ' + class_str
        if self._template_type is not None:
            class_str += ' <{0}>'.format(self._template_type)
        return class_str

# %% Class member


class ClassMember(ContainerMember):
    """Class member (variable and method) representation

    This class is the base class for class members.  The representation
    includes the member type (variable or method), name, scope (``public``,
    ``private`` or ``protected``) and a static flag.

    """
    def __init__(self, class_member, member_scope='private'):
        """Constructor

        Parameters
        ----------
        class_member : CppVariable or CppMethod
            Parsed member object (variable or method)
        member_scope : str
            Member scope property: ``public``, ``private`` or ``protected``
        """
        super().__init__(class_member['name'])
        self._type = None
        self._static = class_member['static']
        self._scope = member_scope
        self._properties = []

    def render(self):
        """Get string representation of member

        The string representation is with the scope indicator and a static
        keyword when the member is static.  It is postfixed by the type (return
        type for class methods) and additional properties (e.g. ``const``
        methods are flagged with the ``query`` property).  The inner part of
        the returned string contains the variable name and signature for
        methods.  This is obtained using the :func:`_render_name` method.

        Returns
        -------
        str
            String representation of member

        """
        if len(self._properties) > 0:
            props = ' {' + ', '.join(self._properties) + '}'
        else:
            props = ''
        vis = MEMBER_PROP_MAP[self._scope] + \
              ('{static} ' if self._static else '')
        member_str = vis + self._render_name() + \
                     (' : ' + self._type if self._type else '') + \
                     props
        return member_str

    def _render_name(self):
        """Get member name

        By default (for member variables), this returns the member name.
        Derived classes can override this to control the name rendering
        (e.g. add the function prototype for member functions)
        """
        return self._name

# %% Class variable


class ClassVariable(ClassMember):
    """Object representation of class member variables

    This class specializes the `ClassMember` object for member variables.
    Additionally to the base class, it stores variable types as strings.  This
    is used to establish aggregation relationships between objects.
    """
    def __init__(self, class_variable, member_scope='private'):
        """Constructor

        Parameters
        ----------
        class_variable : CppVariable
            Parsed class variable object
        member_scope : str
            Scope property to member variable
        """
        assert(isinstance(class_variable,
                          CppHeaderParser.CppHeaderParser.CppVariable))

        super().__init__(class_variable, member_scope)

        self._type = _cleanup_type(class_variable['type'])

    def get_type(self):
        """Variable type accessor

        Returns
        -------
        str
            Variable type as string
        """
        return self._type

# %% Class method


class ClassMethod(ClassMember):
    """Class member method representation

    This class extends `ClassMember` for member methods.  It stores additional
    method properties (abstract, destructor flag, input parameter types).
    """
    def __init__(self, class_method, member_scope):
        """Constructor

        The method name and additional properties are extracted from the parsed
        header.

        * A list of parameter types is stored to retain the function signature.
        * The ``~`` character is appended to destructor methods.
        * ``const`` methods are flagged with the ``query`` property.

        Parameters
        ----------
        class_method : CppMethod
            Parsed class member method
        member_scope : str
            Scope of the member method

        """
        assert(isinstance(class_method,
                          CppHeaderParser.CppHeaderParser.CppMethod))

        super().__init__(class_method, member_scope)

        self._type = _cleanup_type(class_method['returns'])
        if class_method['returns_pointer']:
            self._type += '*'
        elif class_method['returns_reference']:
            self._type += '&'
        self._abstract = class_method['pure_virtual']
        if class_method['destructor']:
            self._name = '~' + self._name
        if class_method['const']:
            self._properties.append('query')
        self._param_list = []
        for param in class_method['parameters']:
            self._param_list.append([_cleanup_type(param['type']),
                                     param['name']])

    def _render_name(self):
        """Internal rendering of method name

        This method extends the base :func:`ClassMember._render_name` method by
        adding the method signature to the returned string.

        Returns
        -------
        str
            The method name (prefixed with the ``abstract`` keyword when
            appropriate) and signature
        """
        assert(not self._static or not self._abstract)

        method_str = ('{abstract} ' if self._abstract else '') + \
                     self._name + '(' + \
                     ', '.join(' '.join(it).strip()
                               for it in self._param_list) + ')'

        return method_str

# %% Struct object


class Struct(Class):
    """Representation of C++ struct objects

    This class derived is almost identical to `Class`, the only difference
    being the container type name ("struct" instead of "class").
    """
    def __init__(self, header_struct):
        """Class constructor

        Parameters
        ----------
        header_struct : list (str, CppStruct)
            Parsed header for struct object (two-element list where the first
            element is the structure name and the second element is a CppStruct
            object)
        """
        super().__init__(header_struct[0])
        super(Class).__init__('struct')

# %% Enum object


class Enum(Container):
    """Class representing enum objects

    This class defines a simple object inherited from the base `Container`
    class.  It simply lists enumerated values.
    """
    def __init__(self, header_enum):
        """Constructor

        Parameters
        ----------
        header_enum : CppEnum
            Parsed CppEnum object
        """
        super().__init__('enum', header_enum.get('name', 'empty'))
        self.parse_members(header_enum)

    def _do_parse_members(self, header_enum):
        """Extract enum values from header

        Parameters
        ----------
        header_enum : CppEnum
            Parsed `CppEnum` object
        """
        for value in header_enum.get('values', []):
            self._member_list.append(EnumValue(value['name']))


class EnumValue(ContainerMember):
    """Class representing values in enum object

    This class only contains the name of the enum value (the actual integer
    value is ignored).
    """
    def __init__(self, header_value, **kwargs):
        """Constructor

        Parameters
        ----------
        header_value : str
            Name of enum member
        """
        super().__init__(header_value)

    def render(self):
        """Rendering to string

        This method simply returns the variable name

        Returns
        -------
        str
            The enumeration element name
        """
        return self._name

# %% Class connections


class ClassRelationship(object):
    """Base object for class relationships

    This class defines the common structure of class relationship objects.
    This includes a parent/child pair and a relationship type (e.g. inheritance
    or aggregation).
    """
    def __init__(self, link_type, c_parent, c_child, flag_use_namespace=False):
        """Constructor

        Parameters
        ----------
        link_type : str
            Relationship type: ``inherit`` or ``aggregation``
        c_parent : str
            Name of parent class
        c_child : str
            Name of child class
        """
        self._parent = c_parent.get_name()
        self._child = c_child.get_name()
        self._link_type = link_type
        self._parent_namespace = c_parent._namespace or None
        self._child_namespace = c_child._namespace or None
        self._flag_use_namespace = flag_use_namespace

    def comparison_keys(self):
        """Order comparison key between `ClassRelationship` objects

        Compare alphabetically based on the parent name, the child name then
        the link type.

        Returns
        -------
        list
            `operator.attrgetter` objects for successive fields used as keys
        """
        return self._parent, self._child, self._link_type

    def _render_name(self, class_name, class_namespace, flag_use_namespace):
        """Render class name with namespace prefix if necessary

        Parameters
        ----------
        class_name : str
           Name of the class
        class_namespace : str
            Namespace or None if the class is defined in the default namespace
        flag_use_namespace : bool
            When False, do not use the namespace

        Returns
        -------
        str
            Class name with appropriate prefix for use with link rendering
        """
        if not flag_use_namespace:
            return class_name

        if class_namespace is None:
            prefix = '.'
        else:
            prefix = class_namespace + '.'
        return prefix + class_name

    def render(self):
        """Render class relationship to string

        This method generically appends the parent name, a rendering of the
        link type (obtained from the :func:`_render_link_type` method) and the
        child object name.

        Returns
        -------
        str
            The string representation of the class relationship following the
            PlantUML syntax
        """
        link_str = ''

        # Wrap the link in namespace block (if both parent and child are in the
        # same namespace)
        namespace_wrap = None
        if self._parent_namespace == self._child_namespace and \
           self._parent_namespace is not None:
            namespace_wrap = self._parent_namespace

        # Prepend the namespace to the class name
        flag_render_namespace = self._flag_use_namespace and not namespace_wrap
        parent_str = self._render_name(self._parent, self._parent_namespace,
                                       flag_render_namespace)
        child_str = self._render_name(self._child, self._child_namespace,
                                      flag_render_namespace)

        # Link string
        link_str += parent_str + ' ' + self._render_link_type() + \
                    ' ' + child_str + '\n'

        if namespace_wrap is not None:
            return wrap_namespace(link_str, namespace_wrap)
        return link_str

    def _render_link_type(self):
        """Internal representation of link

        The string representation is obtained from the `LINK_TYPE_MAP`
        constant.

        Returns
        -------
        str
            The link between parent and child following the PlantUML syntax
        """
        return LINK_TYPE_MAP[self._link_type]

# %% Class inheritance


class ClassInheritanceRelationship(ClassRelationship):
    """Representation of inheritance relationships

    This module extends the base `ClassRelationship` class by setting the link
    type to ``inherit``.
    """
    def __init__(self, c_parent, c_child, **kwargs):
        """Constructor

        Parameters
        ----------
        c_parent : str
            Parent class
        c_child : str
            Derived class
        kwargs : dict
            Additional parameters passed to parent class
        """
        super().__init__('inherit', c_parent, c_child, **kwargs)

# %% Class aggregation


class ClassAggregationRelationship(ClassRelationship):
    """Representation of aggregation relationships

    This module extends the base `ClassRelationship` class by setting the link
    type to ``aggregation``.  It also keeps a count of aggregation, which is
    displayed near the arrow when using PlantUML.

    Aggregation relationships are simplified to represent the presence of a
    variable type (possibly within a container such as a list) in a class
    definition.
    """
    def __init__(self, c_object, c_container, c_count=1,
                 rel_type='aggregation', **kwargs):
        """Constructor

        Parameters
        ----------
        c_object : str
            Class corresponding to the type of the member variable in the
            aggregation relationship
        c_container : str
            Child (or client) class of the aggregation relationship
        c_count : int
            The number of members of ``c_container`` that are of type (possibly
            through containers) ``c_object``
        rel_type : str
            Relationship type: ``aggregation`` or ``composition``
        kwargs : dict
            Additional parameters passed to parent class
        """
        super().__init__(rel_type, c_object, c_container, **kwargs)
        self._count = c_count

    def _render_link_type(self):
        """Internal link rendering

        This method overrides the default link rendering defined in
        :func:`ClassRelationship._render_link_type` to include a count near the
        end of the arrow.
        """
        count_str = '' if self._count == 1 else '"%d" ' % self._count
        return count_str + LINK_TYPE_MAP[self._link_type]

# %% Class dependency


class ClassDependencyRelationship(ClassRelationship):
    """Dependency relationship

    Dependencies occur when member methods depend on an object of another class
    in the diagram.
    """
    def __init__(self, c_parent, c_child, **kwargs):
        """Constructor

        Parameters
        ----------
        c_parent : str
            Class corresponding to the type of the member variable in the
            dependency relationship
        c_child : str
            Child (or client) class of the dependency relationship
        kwargs : dict
            Additional parameters passed to parent class
        """
        super().__init__('dependency', c_parent, c_child, **kwargs)

# %% Diagram class


class Diagram(object):
    """UML diagram object

    This class lists the objects in the set of files considered, and the
    relationships between object.

    The main interface to the `Diagram` object is via the ``create_*`` and
    ``add_*`` methods.  The former parses objects and builds relationship lists
    between the different parsed objects.  The latter only parses objects and
    does not builds relationship lists.

    Each method has versions for file and string inputs and folder string lists
    and file lists inputs.
    """
    def __init__(self, template_file=None, flag_dep=False):
        """Constructor

        The `Diagram` class constructor simply initializes object lists.  It
        does not create objects or relationships.
        """
        self._flag_dep = flag_dep
        self.clear()
        loader_list = []
        if template_file is not None:
            loader_list.append(jinja2.FileSystemLoader(
                os.path.abspath(os.path.dirname(template_file))))
            self._template_file = os.path.basename(template_file)
        else:
            self._template_file = 'default.puml'
        loader_list.append(jinja2.PackageLoader('hpp2plantuml', 'templates'))
        self._env = jinja2.Environment(loader=jinja2.ChoiceLoader(
            loader_list), keep_trailing_newline=True)

    def clear(self):
        """Reinitialize object"""
        self._objects = []
        self._inheritance_list = []
        self._aggregation_list = []
        self._dependency_list = []

    def _sort_list(input_list):
        """Sort list using `ClassRelationship` comparison

        Parameters
        ----------
        input_list : list(ClassRelationship)
            Sort list using the :func:`ClassRelationship.comparison_keys`
            comparison function
        """
        input_list.sort(key=lambda obj: obj.comparison_keys())

    def sort_elements(self):
        """Sort elements in diagram

        Sort the objects and relationship links.  Objects are sorted using the
        :func:`Container.comparison_keys` comparison function and list are
        sorted using the `_sort_list` helper function.
        """
        self._objects.sort(key=lambda obj: obj.comparison_keys())
        for obj in self._objects:
            obj.sort_members()
        Diagram._sort_list(self._inheritance_list)
        Diagram._sort_list(self._aggregation_list)
        Diagram._sort_list(self._dependency_list)

    def _build_helper(self, input, build_from='string', flag_build_lists=True,
                      flag_reset=False):
        """Helper function to initialize a `Diagram` object from parsed headers

        Parameters
        ----------
        input : CppHeader or str or list(CppHeader) or list(str)
            Input of arbitrary type.  The processing depends on the
            ``build_from`` parameter
        build_from : str
            Determines the type of the ``input`` variable:

            * ``string``: ``input`` is a string containing C++ header code
            * ``file``: ``input`` is a filename to parse
            * ``string_list``: ``input`` is a list of strings containing C++
              header code
            * ``file_list``: ``input`` is a list of filenames to parse

        flag_build_lists : bool
            When True, relationships lists are built and the objects in the
            diagram are sorted, otherwise, only object parsing is performed
        flag_reset : bool
            If True, the object is initialized (objects and relationship lists
            are cleared) prior to parsing objects, otherwise, new objects are
            appended to the list of existing ones
        """
        if flag_reset:
            self.clear()
        if build_from in ('string', 'file'):
            self.parse_objects(input, build_from)
        elif build_from in ('string_list', 'file_list'):
            print("ddddddddddddddddddddddddddddddddddddddddddd")
            print(input)
            build_from_single = re.sub('_list$', '', build_from)
            print("build_from_single: " + build_from_single)
            for single_input in input:
                print("  - " + single_input)
                self.parse_objects(single_input, build_from_single)
            print("ddddddddddddddddddddddddddddddddddddddddddd")
        if flag_build_lists:
            self.build_relationship_lists()
            self.sort_elements()

    def create_from_file(self, header_file):
        """Initialize `Diagram` object from header file

        Wrapper around the :func:`_build_helper` function, with ``file`` input,
        building the relationship lists and with object reset.
        """
        self._build_helper(header_file, build_from='file',
                           flag_build_lists=True, flag_reset=True)

    def create_from_file_list(self, file_list):
        """Initialize `Diagram` object from list of header files

        Wrapper around the :func:`_build_helper` function, with ``file_list``
        input, building the relationship lists and with object reset.
        """
        print("ccccccccccccccccccccccccccccccccccccccccccc")
        print file_list
        print("ccccccccccccccccccccccccccccccccccccccccccc")
        self._build_helper(file_list, build_from='file_list',
                           flag_build_lists=True, flag_reset=True)

    def add_from_file(self, header_file):
        """Augment `Diagram` object from header file

        Wrapper around the :func:`_build_helper` function, with ``file`` input,
        skipping building of the relationship lists and without object reset
        (new objects are added to the object).
        """
        self._build_helper(header_file, build_from='file',
                           flag_build_lists=False, flag_reset=False)

    def add_from_file_list(self, file_list):
        """Augment `Diagram` object from list of header files

        Wrapper around the :func:`_build_helper` function, with ``file_list``
        input, skipping building of the relationship lists and without object
        reset (new objects are added to the object).
        """
        self._build_helper(file_list, build_from='file_list',
                           flag_build_lists=False, flag_reset=False)

    def create_from_string(self, header_string):
        """Initialize `Diagram` object from header string

        Wrapper around the :func:`_build_helper` function, with ``string``
        input, building the relationship lists and with object reset.
        """
        self._build_helper(header_string, build_from='string',
                           flag_build_lists=True, flag_reset=True)

    def create_from_string_list(self, string_list):
        """Initialize `Diagram` object from list of header strings

        Wrapper around the :func:`_build_helper` function, with ``string_list``
        input, skipping building of the relationship lists and with object
        reset.
        """
        self._build_helper(string_list, build_from='string_list',
                           flag_build_lists=True, flag_reset=True)

    def add_from_string(self, header_string):
        """Augment `Diagram` object from header string

        Wrapper around the :func:`_build_helper` function, with ``string``
        input, skipping building of the relationship lists and without object
        reset (new objects are added to the object).
        """
        self._build_helper(header_string, build_from='string',
                           flag_build_lists=False, flag_reset=False)

    def add_from_string_list(self, string_list):
        """Augment `Diagram` object from list of header strings

        Wrapper around the :func:`_build_helper` function, with ``string_list``
        input, building the relationship lists and without object reset (new
        objects are added to the object).
        """
        self._build_helper(string_list, build_from='string_list',
                           flag_build_lists=False, flag_reset=False)

    def build_relationship_lists(self):
        """Build inheritance and aggregation lists from parsed objects

        This method successively calls the :func:`build_inheritance_list` and
        :func:`build_aggregation_list` methods.
        """
        self.build_inheritance_list()
        self.build_aggregation_list()
        if self._flag_dep:
            self.build_dependency_list()

    def parse_objects(self, header_file, arg_type='string'):
        """Parse objects

        This method parses file of string inputs using the CppHeaderParser
        module and extracts internal objects for rendering.

        Parameters
        ----------
        header_file : str
            A string containing C++ header code or a filename with C++ header
            code
        arg_type : str
            It set to ``string``, ``header_file`` is considered to be a string,
            otherwise, it is assumed to be a filename
        """
        # Parse header file

        print("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
        print("  header_file: " + header_file)
        print("  arg_type: " + arg_type)
        print("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
        parsed_header = CppHeaderParser.CppHeader(header_file,
                                                  argType=arg_type)
        print("fffffffffffffffffffffffffffffffffffffffffff")
        print("parsed_header: ")
        #print(parsed_header)
        print("fffffffffffffffffffffffffffffffffffffffffff")
        for container_type, container_iterator, \
            container_handler in CONTAINER_TYPE_MAP:
            objects = parsed_header.__getattribute__(container_type)
            print("ggggggggggggggggggggggggggggggggggggggggggg")
            print("  objects:")
            print(objects)
            print("ggggggggggggggggggggggggggggggggggggggggggg")
            for obj in container_iterator(objects):
                print("hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")
                print("  obj:")
                print(obj)
                print("hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh")
                self._objects.append(container_handler(obj))
                print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")


    def _make_class_list(self):
        """Build list of classes

        Returns
        -------
        list(dict)
            Each entry is a dictionary with keys ``name`` (class name) and
            ``obj`` the instance of the `Class` class
        """
        return [{'name': obj.get_name(), 'obj': obj}
                for obj in self._objects if isinstance(obj, Class)]

    def build_inheritance_list(self):
        """Build list of inheritance between objects

        This method lists all the inheritance relationships between objects
        contained in the `Diagram` object (external relationships are ignored).

        The implementation establishes a list of available classes and loops
        over objects to obtain their inheritance.  When parent classes are in
        the list of available classes, a `ClassInheritanceRelationship` object
        is added to the list.
        """
        self._inheritance_list = []
        # Build list of classes in diagram
        class_list_obj = self._make_class_list()
        class_list = [c['name'] for c in class_list_obj]
        flag_use_namespace = any([c['obj']._namespace for c in class_list_obj])

        # Create relationships

        # Inheritance
        for obj in self._objects:
            obj_name = obj.get_name()
            if isinstance(obj, Class):
                for parent in obj.build_inheritance_list():
                    if parent in class_list:
                        parent_obj = class_list_obj[
                            class_list.index(parent)]['obj']
                        self._inheritance_list.append(
                            ClassInheritanceRelationship(
                                parent_obj, obj,
                                flag_use_namespace=flag_use_namespace))

    def build_aggregation_list(self):
        """Build list of aggregation relationships

        This method loops over objects and finds members with type
        corresponding to other classes defined in the `Diagram` object (keeping
        a count of occurrences).

        The procedure first builds an internal dictionary of relationships
        found, augmenting the count using the :func:`_augment_comp` function.
        In a second phase, `ClassAggregationRelationship` objects are created
        for each relationships, using the calculated count.
        """
        self._aggregation_list = []
        # Build list of classes in diagram
        # Build list of classes in diagram
        class_list_obj = self._make_class_list()
        class_list = [c['name'] for c in class_list_obj]
        flag_use_namespace = any([c['obj']._namespace for c in class_list_obj])

        # Build member type list
        variable_type_list = {}
        for obj in self._objects:
            obj_name = obj.get_name()
            if isinstance(obj, Class):
                variable_type_list[obj_name] = obj.build_variable_type_list()
        # Create aggregation links
        aggregation_counts = {}

        for child_class in class_list:
            if child_class in variable_type_list.keys():
                var_types = variable_type_list[child_class]
                for var_type in var_types:
                    for parent in class_list:
                        if re.search(r'\b' + parent + r'\b', var_type):
                            rel_type = 'composition'
                            if '{}*'.format(parent) in var_type:
                                rel_type = 'aggregation'
                            self._augment_comp(aggregation_counts, parent,
                                               child_class, rel_type=rel_type)
        for obj_class, obj_comp_list in aggregation_counts.items():
            for comp_parent, rel_type, comp_count in obj_comp_list:
                obj_class_idx = class_list.index(obj_class)
                obj_class_obj = class_list_obj[obj_class_idx]['obj']
                comp_parent_idx = class_list.index(comp_parent)
                comp_parent_obj = class_list_obj[comp_parent_idx]['obj']
                self._aggregation_list.append(
                    ClassAggregationRelationship(
                        obj_class_obj, comp_parent_obj, comp_count,
                        rel_type=rel_type,
                        flag_use_namespace=flag_use_namespace))

    def build_dependency_list(self):
        """Build list of dependency between objects

        This method lists all the dependency relationships between objects
        contained in the `Diagram` object (external relationships are ignored).

        The implementation establishes a list of available classes and loops
        over objects, list their methods adds a dependency relationship when a
        method takes an object as input.
        """

        self._dependency_list = []
        # Build list of classes in diagram
        class_list_obj = self._make_class_list()
        class_list = [c['name'] for c in class_list_obj]
        flag_use_namespace = any([c['obj']._namespace for c in class_list_obj])

        # Create relationships

        # Add all objects name to list
        objects_name = []
        for obj in self._objects:
            objects_name.append(obj.get_name())

        # Dependency
        for obj in self._objects:
            if isinstance(obj, Class):
                for member in obj._member_list:
                    # Check if the member is a method
                    if isinstance(member, ClassMethod):
                        for method in member._param_list:
                            index = ValueError
                            try:
                                # Check if the method param type is a Class
                                # type
                                index = [re.search(o, method[0]) is not None
                                         for o in objects_name].index(True)
                            except ValueError:
                                pass
                            if index != ValueError and \
                               method[0] != obj.get_name():
                                depend_obj = self._objects[index]

                                self._dependency_list.append(
                                    ClassDependencyRelationship(
                                        depend_obj, obj,
                                        flag_use_namespace=flag_use_namespace))

    def _augment_comp(self, c_dict, c_parent, c_child, rel_type='aggregation'):
        """Increment the aggregation reference count

        If the aggregation relationship is not in the list (``c_dict``), then
        add a new entry with count 1.  If the relationship is already in the
        list, then increment the count.

        Parameters
        ----------
        c_dict : dict
            List of aggregation relationships.  For each dictionary key, a pair
            of (str, int) elements: string and number of occurrences
        c_parent : str
            Parent class name
        c_child : str
            Child class name
        rel_type : str
            Relationship type: ``aggregation`` or ``composition``
        """
        if c_child not in c_dict:
            c_dict[c_child] = [[c_parent, rel_type, 1], ]
        else:
            parent_list = [c[:2] for c in c_dict[c_child]]
            if [c_parent, rel_type] not in parent_list:
                c_dict[c_child].append([c_parent, rel_type, 1])
            else:
                c_idx = parent_list.index([c_parent, rel_type])
                c_dict[c_child][c_idx][2] += 1

    def render(self):
        """Render full UML diagram

        The string returned by this function should be ready to use with the
        PlantUML program.  It includes all the parsed objects with their
        members, and the inheritance and aggregation relationships extracted
        from the list of objects.

        Returns
        -------
        str
            String containing the full string representation of the `Diagram`
            object, including objects and object relationships
        """
        template = self._env.get_template(self._template_file)
        return template.render(objects=self._objects,
                               inheritance_list=self._inheritance_list,
                               aggregation_list=self._aggregation_list,
                               dependency_list=self._dependency_list,
                               flag_dep=self._flag_dep)

# %% Cleanup object type string


def _cleanup_type(type_str):
    """Cleanup string representing a C++ type

    Cleanup simply consists in removing spaces before a ``*`` character and
    preventing multiple successive spaces in the string.

    Parameters
    ----------
    type_str : str
        A string representing a C++ type definition

    Returns
    -------
    str
        The type string after cleanup
    """
    return re.sub(r'[ ]+([*&])', r'\1',
                  re.sub(r'(\s)+', r'\1', type_str))

# %% Single line version of string


def _cleanup_single_line(input_str):
    """Cleanup string representing a C++ type

    Remove line returns

    Parameters
    ----------
    input_str : str
        A string possibly spreading multiple lines

    Returns
    -------
    str
        The type string in a single line
    """
    return re.sub(r'\s+', ' ', re.sub(r'(\r)?\n', ' ', input_str))

# %% Expand wildcards in file list


def expand_file_list(input_files):
    """Find all files in list (expanding wildcards)

    This function uses `glob` to find files matching each string in the input
    list.

    Parameters
    ----------
    input_files : list(str)
        List of strings representing file names and possibly including
        wildcards

    Returns
    -------
    list(str)
        List of filenames (with wildcards expanded).  Each element contains the
        name of an existing file
    """
    file_list = []
    for input_file in input_files:
        file_list += glob.glob(input_file)
        print("Input File: " + input_file)
    return file_list

def wrap_namespace(input_str, namespace):
    """Wrap string in namespace

    Parameters
    ----------
    input_str : str
        String containing PlantUML code
    namespace : str
       Namespace name

    Returns
    -------
    str
        ``input_str`` wrapped in ``namespace`` block
    """
    return 'namespace {} {{\n'.format(namespace) + \
        '\n'.join([re.sub('^', '\t', line)
                   for line in input_str.splitlines()]) + \
        '\n}\n'

# %% Main function


def CreatePlantUMLFile(file_list, output_file=None, **diagram_kwargs):
    """Create PlantUML file from list of header files

    This function parses a list of C++ header files and generates a file for
    use with PlantUML.

    Parameters
    ----------
    file_list : list(str)
        List of filenames (possibly, with wildcards resolved with the
        :func:`expand_file_list` function)
    output_file : str
        Name of the output file
    diagram_kwargs : dict
        Additional parameters passed to :class:`Diagram` constructor
    """

    print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    print("file_list: ")
    print(file_list)
    print("output_file: " + output_file)
    print("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    if isinstance(file_list, str):
        file_list_c = [file_list, ]
    else:
        file_list_c = file_list

    print("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    print("file_list_c: ")
    print(file_list_c)
    print("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    diag = Diagram(**diagram_kwargs)
    diag.create_from_file_list(list(set(expand_file_list(file_list_c))))
    diag_render = diag.render()

    if output_file is None:
        print(diag_render)
    else:
        print("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        print(diag_render)
        print("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        with open(output_file, 'wt') as fid:
            fid.write(diag_render)

# %% Command line interface


def main():
    """Command line interface

    This function is a command-line interface to the
    :func:`hpp2plantuml.CreatePlantUMLFile` function.

    Arguments are read from the command-line, run with ``--help`` for help.
    """
    parser = argparse.ArgumentParser(description='hpp2plantuml tool.')
    parser.add_argument('-i', '--input-file', dest='input_files',
                        action='append', metavar='HEADER-FILE', required=True,
                        help='input file (must be quoted' +
                        ' when using wildcards)')
    parser.add_argument('-o', '--output-file', dest='output_file',
                        required=False, default=None, metavar='FILE',
                        help='output file')
    parser.add_argument('-d', '--enable-dependency', dest='flag_dep',
                        required=False, default=False, action='store_true',
                        help='Extract dependency relationships from method ' +
                        'arguments')
    parser.add_argument('-t', '--template-file', dest='template_file',
                        required=False, default=None, metavar='JINJA-FILE',
                        help='path to jinja2 template file')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + '0.6')
    args = parser.parse_args()
    if len(args.input_files) > 0:
        CreatePlantUMLFile(args.input_files, args.output_file,
                           template_file=args.template_file,
                           flag_dep=args.flag_dep)

# %% Standalone mode


if __name__ == '__main__':
    main()
